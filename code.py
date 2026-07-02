# code.py — CircuitPython servo notifier (runs on the RP2040-Zero).
#
# Servo flag for Claude Code:
#   0   = resting / default
#   180 = Claude finished a task
# Lowers on a command byte "0" (next prompt) or an acknowledge button press.
# Triple-press the button within 2 s to make the arm dance and flash the LED.
import board
import pwmio
import digitalio
import neopixel_write
import supervisor
import sys
import time
import math

SERVO_PIN = board.GP29
BUTTON_PIN = board.GP0          # external acknowledge button to GND
PWM_FREQ_HZ = 50

MIN_PULSE_US = 500
MAX_PULSE_US = 2500
PERIOD_US = 1_000_000 // PWM_FREQ_HZ

IDLE_ANGLE = 0
ALERT_ANGLE = 180
SETTLE_MS = 600

# Flip if the servo turns the wrong way (mirrors every angle end-to-end).
REVERSED = True

# While Claude is thinking, pulse the LED white at this rate (Hz).
# 1/3 Hz = one full fade up-and-down every 3 seconds.
THINK_HZ = 1 / 3

# Triple-press "dance": three debounced presses inside this window triggers it.
TRIPLE_WINDOW_S = 2.0
TRIPLE_COUNT = 3
DEBOUNCE_S = 0.05               # ignore contact bounce between counted presses

# Dance choreography: paired servo angles and onboard-LED colors (R, G, B).
DANCE_MOVES = (
    30, 150, 60, 120, 0, 180, 90,
    45, 135, 75, 160, 20, 110, 90,
)
DANCE_COLORS = (
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (0, 255, 255), (255, 0, 255), (255, 255, 255),
    (255, 128, 0), (128, 0, 255), (0, 255, 128), (255, 0, 128),
    (128, 255, 0), (0, 128, 255), (255, 255, 255),
)
DANCE_STEP_S = 0.22

pwm = pwmio.PWMOut(SERVO_PIN, frequency=PWM_FREQ_HZ)

# Onboard WS2812 RGB LED (GP16). Driven directly via the core neopixel_write
# module so no external library is required.
led = digitalio.DigitalInOut(board.NEOPIXEL)
led.direction = digitalio.Direction.OUTPUT


def led_rgb(r, g, b):
    # The WS2812 expects color bytes in GRB order.
    neopixel_write.neopixel_write(led, bytearray((g, r, b)))


def set_angle(angle):
    angle = max(0, min(180, angle))
    if REVERSED:
        angle = 180 - angle
    pulse = MIN_PULSE_US + (MAX_PULSE_US - MIN_PULSE_US) * angle // 180
    pwm.duty_cycle = int(pulse * 65535 // PERIOD_US)


# Non-blocking move: command the angle now and schedule the "relax" (stop
# sending pulses to kill buzz/holding current) for later, so the main loop
# stays responsive enough to catch rapid button presses.
relax_at = None


def command_angle(angle):
    global relax_at
    set_angle(angle)
    relax_at = time.monotonic() + SETTLE_MS / 1000


def move_to(angle):
    # Blocking move — used at startup and inside the dance, where the loop
    # doesn't need to stay responsive.
    set_angle(angle)
    time.sleep(SETTLE_MS / 1000)
    pwm.duty_cycle = 0


def show_alert():
    # Claude finished: raise the flag and light the LED white.
    led_rgb(255, 255, 255)
    command_angle(ALERT_ANGLE)


def show_idle():
    # Resting / acknowledged: lower the flag and turn the LED off.
    led_rgb(0, 0, 0)
    command_angle(IDLE_ANGLE)


def dance():
    for angle, color in zip(DANCE_MOVES, DANCE_COLORS):
        led_rgb(*color)
        set_angle(angle)
        time.sleep(DANCE_STEP_S)
    led_rgb(0, 0, 0)            # lights off
    move_to(IDLE_ANGLE)        # settle back home and relax


# Start in the resting position with the LED off.
move_to(IDLE_ANGLE)
led_rgb(0, 0, 0)

# Acknowledge button: reads HIGH via pull-up, LOW when pressed to GND.
button = digitalio.DigitalInOut(BUTTON_PIN)
button.switch_to_input(pull=digitalio.Pull.UP)

prev_pressed = False
press_times = []
thinking = False                       # pulse the LED white while Claude works

while True:
    n = supervisor.runtime.serial_bytes_available
    if n:
        data = sys.stdin.read(n)
        if "0" in data:
            thinking = False
            show_idle()
        elif "2" in data:              # Claude is thinking / working
            thinking = True
            command_angle(IDLE_ANGLE)  # flag stays down while it works
        elif data:  # "1" or any other byte -> finished / needs you
            thinking = False
            show_alert()

    pressed = not button.value
    if pressed and not prev_pressed:
        now = time.monotonic()
        # Debounce, then keep only the presses still inside the window.
        if not press_times or now - press_times[-1] >= DEBOUNCE_S:
            press_times = [t for t in press_times if now - t <= TRIPLE_WINDOW_S]
            press_times.append(now)
            if len(press_times) >= TRIPLE_COUNT:
                thinking = False
                dance()
                press_times = []
                relax_at = None        # dance already relaxed the servo
            else:
                thinking = False
                show_idle()
    prev_pressed = pressed

    # While thinking, pulse the LED white at THINK_HZ (smooth 0->full->0).
    if thinking:
        level = (1 - math.cos(2 * math.pi * THINK_HZ * time.monotonic())) / 2
        v = int(255 * level)
        led_rgb(v, v, v)

    # Non-blocking relax once the servo has had time to reach its target.
    if relax_at is not None and time.monotonic() >= relax_at:
        pwm.duty_cycle = 0
        relax_at = None

    time.sleep(0.02)
