#!/bin/bash
# flash.sh — flash a Waveshare RP2040-Zero with the Clawd servo notifier.
#
# What it does, end to end:
#   1. Waits for a board in BOOTSEL/bootloader mode (the RPI-RP2 drive).
#   2. Flashes CircuitPython (copies the .uf2).
#   3. Copies all project files (boot.py, code.py, install.sh, README.md,
#      servo_notify.py) onto the drive.
#   4. Resets the board so boot.py applies the USB identity and renames the
#      drive from CIRCUITPY to CLAWDBOT.
#   5. Verifies the rename.
#
# Usage:  bash flash.sh        (hold BOOTSEL while plugging in if needed)
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
UF2="$SRC_DIR/cp_waveshare_rp2040_zero-10.2.1.uf2"
FILES=(boot.py code.py install.sh servo_notify.py)
BOARD_README="README.board.md"   # deployed to the drive as README.md
NEW_LABEL="CLAWDBOT"
BOOTLOADER="/Volumes/RPI-RP2"

say()  { printf '\n\033[1m→ %s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# --- preflight ---------------------------------------------------------------
[ -f "$UF2" ] || die "firmware not found: $UF2"
for f in "${FILES[@]}" "$BOARD_README"; do
  [ -f "$SRC_DIR/$f" ] || die "missing project file: $f"
done
# Pick a Python that actually has pyserial. The default `python3` may be a
# broken or pyserial-less install (e.g. a fresh Homebrew python), so probe
# candidates and fall back to the macOS system python.
PYBIN=""
for cand in /usr/bin/python3 python3 python3.12 python3.11 python3.10 python3.9; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import serial" >/dev/null 2>&1; then
    PYBIN="$cand"; break
  fi
done
[ -n "$PYBIN" ] || die "no Python with pyserial found — run: /usr/bin/python3 -m pip install --user pyserial"
ok "using Python: $PYBIN"

# --- 1. get the board into the bootloader -----------------------------------
# A blank board auto-boots into the bootloader. A board already running
# CircuitPython can be dropped into the bootloader over USB serial — no need
# to physically hold BOOTSEL.
enter_bootloader() {
  "$PYBIN" - <<'PY' || true
import serial, serial.tools.list_ports, time
port = None
for p in serial.tools.list_ports.comports():
    if "usbmodem" in (p.device or ""):
        port = p.device
if not port:
    raise SystemExit
s = serial.Serial(port, 115200, timeout=0.3); time.sleep(0.2)
# code.py reads stdin, so a single Ctrl-C can be consumed instead of breaking
# to the REPL — send several and settle before issuing commands.
s.write(b"\x03\x03\x03"); time.sleep(0.5); s.reset_input_buffer()
s.write(b"import microcontroller\r"); time.sleep(0.3)
s.write(b"microcontroller.on_next_reset(microcontroller.RunMode.BOOTLOADER)\r"); time.sleep(0.3)
s.write(b"microcontroller.reset()\r"); time.sleep(0.5)
s.close()
PY
}

if [ ! -d "$BOOTLOADER" ] && ls /dev/cu.usbmodem* >/dev/null 2>&1; then
  say "Board is running CircuitPython — sending it to the bootloader (no button needed)..."
  enter_bootloader
fi

say "Waiting for a board in bootloader mode (RPI-RP2)..."
echo "  Tip: only if no board is connected at all, hold BOOTSEL while plugging in."
until [ -d "$BOOTLOADER" ]; do sleep 1; done
ok "bootloader detected"

# --- 2. flash CircuitPython --------------------------------------------------
say "Flashing CircuitPython..."
cp "$UF2" "$BOOTLOADER/" && sync
ok "firmware copied; board rebooting into CircuitPython"

# --- 3. wait for the data drive to mount ------------------------------------
# Flashing the UF2 preserves the filesystem, so a board that already had our
# renaming boot.py comes back as CLAWDBOT, not CIRCUITPY — accept either.
say "Waiting for the board's data drive..."
DRV=""
for _ in $(seq 1 30); do
  for cand in /Volumes/CIRCUITPY "/Volumes/$NEW_LABEL"; do
    [ -d "$cand" ] && { DRV="$cand"; break 2; }
  done
  sleep 1
done
[ -n "$DRV" ] || die "no CircuitPython drive mounted after flash"
sleep 2                      # let the filesystem settle
ok "mounted at $DRV"

# --- 4. copy project files ---------------------------------------------------
say "Copying project files..."
for f in "${FILES[@]}"; do
  cp "$SRC_DIR/$f" "$DRV/$f"
  ok "$f"
done
cp "$SRC_DIR/$BOARD_README" "$DRV/README.md"   # board-facing README
ok "README.md (from $BOARD_README)"
sync
sleep 3                      # let writes settle (relabel skips on a busy FS)

# --- 5. reset so boot.py renames the drive ----------------------------------
# boot.py only runs on a hard reset, and the relabel is skipped if the
# filesystem is still busy from the copy above — so reset and retry until the
# drive comes back as CLAWDBOT.
reset_board() {
  "$PYBIN" - <<'PY'
import serial, serial.tools.list_ports, time, sys
port = None
for _ in range(16):                       # wait up to ~8s for the serial port
    for p in serial.tools.list_ports.comports():
        if "usbmodem" in (p.device or ""):
            port = p.device
    if port:
        break
    time.sleep(0.5)
if not port:
    sys.exit("no serial port")
s = serial.Serial(port, 115200, timeout=0.3); time.sleep(0.2)
s.write(b"\x03"); time.sleep(0.3); s.reset_input_buffer()
s.write(b"import microcontroller; microcontroller.reset()\r"); time.sleep(0.5)
s.close()
PY
}

say "Resetting board to apply rename + USB identity..."
FINAL=""
for attempt in 1 2 3; do
  reset_board || true
  for _ in $(seq 1 20); do
    [ -d "/Volumes/$NEW_LABEL" ] && { FINAL="/Volumes/$NEW_LABEL"; break; }
    sleep 1
  done
  [ -n "$FINAL" ] && break
  echo "  (attempt $attempt: not renamed yet, retrying)"
  sleep 2
done

# --- 6. verify ---------------------------------------------------------------
if [ -n "$FINAL" ]; then
  say "Done — drive flashed and renamed to $NEW_LABEL"
  echo "  Files on $FINAL:"
  ls "$FINAL" | grep -vE '^\.' | sed 's/^/    /'
  echo ""
  echo "  Next: wire the button (GP0 -> button -> GND) and run install.sh"
  echo "  from the drive to hook up Claude Code notifications."
else
  printf '\033[33m⚠ Flashed and files copied, but the rename to %s did not apply.\033[0m\n' "$NEW_LABEL"
  echo "  Physically unplug and replug the board to trigger boot.py."
fi
