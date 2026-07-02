# Clawd Notifier Bot

A little servo **flag** (plus the board's onboard RGB LED) that tells you what
Claude Code is doing, from across the room:

| State | Trigger (Claude Code hook) | Flag | LED |
|-------|----------------------------|------|-----|
| **Wants your attention** — finished, needs permission, or asked a question | `Stop`, `Notification` | up (180°) | solid **white** |
| **Working / thinking** — after each tool call, or you sent a new prompt | `PostToolUse`, `UserPromptSubmit` | down (0°) | pulses **white** (⅓ Hz) |
| **Acknowledged** | button press | down (0°) | off |

Attention requests are **ref-counted**: if several are still pending, clearing one
dips the arm and raises it again so you can tell there's more waiting.

Press the button once to lower the flag ("I saw it"). **Triple-press within 2 s**
to make the arm dance and flash the LED through a color show. 🎉

Runs [CircuitPython](https://circuitpython.org/) on a
[Waveshare RP2040-Zero](https://www.waveshare.com/wiki/RP2040-Zero).
The servo uses an [MG90S](https://components101.com/motors/mg90s-metal-gear-servo-motor) 180 degree servo motor.

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
| `README.board.md` | Short end-user README deployed onto the board's drive as `README.md` |
| `servo_notify.py` | Host-side hook script; sends a one-byte command to the board over USB serial |
| `install.sh` | Installs `servo_notify.py` (into an isolated venv) and registers the Claude Code hooks |
| `uninstall.sh` | Reverses `install.sh`: removes the hooks, script, venv, and state (recoverable — backs up + trashes) |
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

This installs the hook script into an isolated venv under `~/.claude/hooks/` (so
it never touches an externally-managed system/Homebrew Python) and registers four
hooks in `~/.claude/settings.json`: `Stop` + `Notification` → raise,
`UserPromptSubmit` + `PostToolUse` → lower.

To remove everything again:

```bash
bash uninstall.sh
```

It backs up `settings.json` and moves removed files to the Trash first, and leaves
the board's firmware untouched.

## How it works

The host hooks send a single byte to the board over USB serial; `code.py` reads
it in its main loop:

| Byte | Meaning | Result |
|------|---------|--------|
| `1` | attention (finished / needs you) | flag up, LED solid white |
| `2` | thinking / working | flag down, LED pulses white |
| `0` | idle | flag down, LED off |

`servo_notify.py` ref-counts attention on the host: `up` sends `1` (solid white);
`down` sends `2` (working pulse) once nothing is pending, or dips (`0`→`1`) when
attention is still pending. The mode is cached so the frequent `PostToolUse`
`down` only refreshes the pulse once instead of hitting the port every tool call.

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
