#!/usr/bin/env python3
# servo_notify.py — installed to ~/.claude/hooks/servo_notify.py
#
# Sends a one-byte command to the MicroPython servo notifier over USB serial:
#   up   (default) -> "1" : raise the flag to 180 deg (Claude finished a task)
#   down           -> "0" : lower the flag to 0 deg   (resting / default state)
#
# Exits 0 even if the board is missing so it never adds noise to Claude Code.
import sys
import time
import serial
import serial.tools.list_ports

# A freshly opened USB CDC port isn't ready to transmit immediately: on macOS
# the first bytes after open are often dropped before the host/device finish
# negotiating. Wait this long after opening before writing.
OPEN_SETTLE_S = 0.3
# Retry open/write a few times so a momentarily busy port (another hook still
# closing, the CIRCUITPY editor, the board mid-move) doesn't drop the signal.
ATTEMPTS = 4
RETRY_DELAY_S = 0.25

# boot.py on the board gives it a custom USB identity (vendor id 0x1209 from
# pid.codes, product "Robot", manufacturer "Clawd"). Match the vendor id first,
# then fall back to the product/manufacturer strings.
NOTIFIER_VID = 0x1209
PRODUCT_HINTS = ("Robot", "Clawd")


def find_port():
    for port in serial.tools.list_ports.comports():
        if port.vid == NOTIFIER_VID:
            return port.device
        haystack = " ".join(
            filter(None, (port.description, port.product, port.manufacturer))
        )
        if any(hint in haystack for hint in PRODUCT_HINTS):
            return port.device
    return None


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "up"
    if arg in ("down", "lower", "idle", "0"):
        byte = b"0"
    elif arg in ("think", "thinking", "working", "2"):
        byte = b"2"  # pulse white while Claude works
    else:
        byte = b"1"

    for attempt in range(ATTEMPTS):
        # Re-resolve the port each attempt: it can disappear/reappear (e.g. the
        # board re-enumerates) between tries.
        port = find_port()
        if not port:
            time.sleep(RETRY_DELAY_S)
            continue
        try:
            with serial.Serial(port, 115200, timeout=1) as s:
                time.sleep(OPEN_SETTLE_S)  # let the CDC link come up
                s.write(byte)
                s.flush()                  # block until the OS hands off the byte
                time.sleep(0.05)           # let it actually drain before close
            sys.exit(0)                    # sent — done
        except serial.SerialException:
            time.sleep(RETRY_DELAY_S)      # port busy; back off and retry

    sys.exit(0)  # board missing or never free — stay quiet, never block Claude


if __name__ == "__main__":
    main()
