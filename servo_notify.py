#!/usr/bin/env python3
# servo_notify.py — installed to ~/.claude/hooks/servo_notify.py
#
# Sends a one-byte command to the MicroPython servo notifier over USB serial:
#   up   (default) -> "1" : raise the flag to 180 deg (Claude wants attention:
#                           finished, needs permission, or asked a question)
#   down           -> "0" : lower the flag to 0 deg   (resting / default state)
#
# Exits 0 even if the board is missing so it never adds noise to Claude Code.
import os
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
# When a down still leaves work pending, lower the arm then raise it again after
# this pause so the dip is physically visible — and so the board reads the two
# bytes as separate commands instead of coalescing "01" into a single lower.
DIP_PAUSE_S = 0.7

# boot.py on the board gives it a custom USB identity (vendor id 0x1209 from
# pid.codes, product "Robot", manufacturer "Clawd"). Match the vendor id first,
# then fall back to the product/manufacturer strings.
NOTIFIER_VID = 0x1209
PRODUCT_HINTS = ("Robot", "Clawd")

# Tracks how many "raise" requests are still pending: "up" increments it, "down"
# decrements it, and the flag is up whenever the count is > 0. This lets a "down"
# that still leaves work pending dip the arm and raise it again, instead of just
# lowering it. It also lets the frequent "down" (fired after every tool call via
# PostToolUse) skip the serial round-trip whenever nothing is pending.
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".servo_state")


def read_count():
    try:
        with open(STATE_FILE) as f:
            return max(0, int(f.read().strip()))
    except (OSError, ValueError):
        return 0


def write_count(count):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(max(0, count)))
    except OSError:
        pass


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


def send_sequence(steps):
    # Open the port and play a list of (byte, pause_after_s) steps in one session.
    # Returns True once the bytes are handed off, False if the board is missing or
    # never frees up. Best-effort: the caller tracks the pending count regardless.
    for attempt in range(ATTEMPTS):
        # Re-resolve the port each attempt: it can disappear/reappear (e.g. the
        # board re-enumerates) between tries.
        port = find_port()
        if not port:
            time.sleep(RETRY_DELAY_S)
            continue
        try:
            with serial.Serial(port, 115200, timeout=1) as s:
                time.sleep(OPEN_SETTLE_S)      # let the CDC link come up
                for byte, pause in steps:
                    s.write(byte)
                    s.flush()                  # block until the OS hands off the byte
                    time.sleep(0.05)           # let it actually drain
                    if pause:
                        time.sleep(pause)
            return True
        except serial.SerialException:
            time.sleep(RETRY_DELAY_S)          # port busy; back off and retry
    return False


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "up"
    up = arg not in ("down", "lower", "idle", "0")
    count = read_count()

    if up:
        # Another attention request: count it and (re)raise the flag. "up" is rare
        # and always sent, so a flag lowered out-of-band by the GP0 button comes
        # back up.
        write_count(count + 1)
        send_sequence([(b"1", 0)])
        sys.exit(0)

    if count == 0:
        # Nothing pending — the arm is already resting. "down" fires after every
        # tool call (PostToolUse), so skip the serial round-trip in this common case.
        sys.exit(0)

    count -= 1
    write_count(count)
    if count == 0:
        send_sequence([(b"0", 0)])                       # last item cleared: rest
    else:
        send_sequence([(b"0", DIP_PAUSE_S), (b"1", 0)])  # still pending: dip + raise

    sys.exit(0)  # board missing or never free -> count is still updated; stay quiet


if __name__ == "__main__":
    main()
