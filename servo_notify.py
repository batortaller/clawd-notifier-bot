#!/usr/bin/env python3
# servo_notify.py — installed to ~/.claude/hooks/servo_notify.py
#
# Sends a one-byte command to the servo notifier over USB serial:
#   up   (default) -> "1" : raise the flag, solid white LED (Claude wants your
#                           attention: finished, needs permission, or asking)
#   down           -> Claude is working: "2" -> flag down + pulsing white LED,
#                     unless attention is still pending, in which case the flag
#                     dips ("0" then "1") to signal there's more waiting.
#
# Exits 0 even if the board is missing so it never adds noise to Claude Code.
import os
import sys
import json
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

# Persisted state: how many "attention" requests are pending ("up" increments,
# "down" decrements — the flag is up while count > 0) plus the LED mode currently
# shown on the board ("attention" or "working"). Tracking the mode lets the
# frequent PostToolUse "down" refresh the working pulse once and then no-op,
# instead of hitting the serial port on every tool call.
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".servo_state")


def read_state():
    try:
        with open(STATE_FILE) as f:
            raw = f.read().strip()
    except OSError:
        return 0, ""
    try:
        data = json.loads(raw)
        return max(0, int(data.get("count", 0))), str(data.get("mode", ""))
    except (ValueError, AttributeError):
        try:
            return max(0, int(raw)), ""   # legacy format: a bare integer count
        except ValueError:
            return 0, ""


def write_state(count, mode):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"count": max(0, count), "mode": mode}, f)
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
    count, mode = read_state()

    if up:
        # Attention request (Stop / Notification): count it and raise the flag,
        # solid white. "up" is always sent, so a flag lowered out-of-band by the
        # GP0 button comes back up.
        write_state(count + 1, "attention")
        send_sequence([(b"1", 0)])
        sys.exit(0)

    # "down" = Claude is working now (UserPromptSubmit / PostToolUse).
    if count > 0:
        count -= 1
        if count > 0:
            # One attention cleared but more remain: dip the flag and raise it
            # again so you can tell there's still something waiting.
            write_state(count, "attention")
            send_sequence([(b"0", DIP_PAUSE_S), (b"1", 0)])
        else:
            # Nothing pending anymore -> show the "thinking" pulse.
            write_state(0, "working")
            send_sequence([(b"2", 0)])
        sys.exit(0)

    # Already nothing pending. Refresh the working pulse once, then let the
    # frequent PostToolUse "down" no-op so we don't spam the serial port.
    if mode != "working":
        write_state(0, "working")
        send_sequence([(b"2", 0)])
    sys.exit(0)  # board missing or never free -> state still updated; stay quiet


if __name__ == "__main__":
    main()
