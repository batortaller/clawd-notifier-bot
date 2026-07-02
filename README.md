# Clawd Notifier Bot

A little servo **flag** (plus the board's onboard RGB LED) that tells you what
Claude Code is doing, from across the room:

| State | Trigger (Claude Code hook) | Flag | LED |
|-------|----------------------------|------|-----|
| **Working / thinking** | `UserPromptSubmit` | down (0°) | pulses **white**, slowly (⅓ Hz) |
| **Finished a task** | `Stop` | up (180°) | solid **white** |
| **Needs you** (asks a question / permission) | `Notification` | up (180°) | solid **white** |
| **Acknowledged** | button press | down (0°) | off |

Press the button once to lower the flag ("I saw it"). **Triple-press within 2 s**
to make the arm dance and flash the LED through a color show. 🎉

Runs [CircuitPython](https://circuitpython.org/) on a
[Waveshare RP2040-Zero](https://www.waveshare.com/wiki/RP2040-Zero).

## Hardware

| Part | Pin | Notes |
|------|-----|-------|
| Servo (signal) | `GP29` | Hobby servo, 50 Hz, 500–2500 µs |
| Servo (power) | `5V` / `VBUS` | **Not `3V3`** — that routes motor current through the regulator and can kill the board |
| Push button | `GP0` → button → `GND` | Uses the internal pull-up; no resistor needed |
| RGB LED | `GP16` (`board.NEOPIXEL`) | Onboard WS2812, driven by the built-in `neopixel_write` |

Powering the servo from USB works, but a servo is an inductive motor: add a
**bulk capacitor (470–1000 µF) across the servo's V+/GND** to absorb current
spikes and back-EMF. Without it, rapid motion (like the dance) can brown out or
damage the board.

## Repository layout

| File | What it is |
|------|------------|
| `code.py` | The firmware — servo + LED state machine, button handling, dance |
| `boot.py` | Sets a custom USB identity and renames the drive to `CLAWDBOT` |
| `servo_notify.py` | Host-side hook script; sends a one-byte command to the board over USB serial |
| `install.sh` | Registers the Claude Code hooks and installs `servo_notify.py` |
| `flash.sh` | One-command flasher: firmware + files + rename, no BOOTSEL button needed |
| `cp_waveshare_rp2040_zero-10.2.1.uf2` | The exact CircuitPython build this is tested against |

## Quick start

### 1. Flash a board

```bash
bash flash.sh
```

Plug the board in (already-running boards are dropped into the bootloader over
USB automatically — no need to hold BOOTSEL). The script flashes CircuitPython,
copies all project files, and renames the drive to `CLAWDBOT`.

Requires **pyserial** on a working Python. `flash.sh` auto-detects an
interpreter that has it and falls back to `/usr/bin/python3`. If none is found:

```bash
/usr/bin/python3 -m pip install --user pyserial
```

### 2. Wire the button

One leg to the `GP0` pad, the other to any `GND` pad.

### 3. Hook it up to Claude Code

```bash
bash install.sh
```

This installs the hook script to `~/.claude/hooks/` and registers three hooks in
`~/.claude/settings.json`: `Stop` and `Notification` → raise, `UserPromptSubmit`
→ pulse-while-working.

## How it works

The host hooks send a single byte to the board over USB serial; `code.py` reads
it in its main loop:

| Byte | Meaning | Result |
|------|---------|--------|
| `1` | alert (finished / needs you) | flag up, LED solid white |
| `2` | thinking / working | flag down, LED pulses white |
| `0` | idle | flag down, LED off |

A button press is handled entirely on the board (single = acknowledge/lower,
triple within 2 s = dance).

## Tuning (all at the top of `code.py`)

| Constant | Purpose |
|----------|---------|
| `REVERSED` | Flip if the servo turns the wrong way |
| `THINK_HZ` | Thinking-pulse rate (default ⅓ Hz) |
| `IDLE_ANGLE` / `ALERT_ANGLE` | Flag down/up positions |
| `TRIPLE_WINDOW_S` / `TRIPLE_COUNT` / `DEBOUNCE_S` | Triple-press gesture |
| `DANCE_MOVES` / `DANCE_COLORS` / `DANCE_STEP_S` | Dance choreography |

## Limitations

This integrates with **Claude Code** (the CLI), which exposes lifecycle *hooks*.
The Claude **desktop app** has no equivalent hook system, so it can't drive the
board.
