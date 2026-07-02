# boot.py — CircuitPython. Runs once at power-on, before USB is presented.
# Gives the board a custom USB identity (custom vendor id + product name) so the
# host hook can find THIS device, and renames the drive to CLAWDBOT.
import supervisor
import storage

# Rename the USB drive from CIRCUITPY to CLAWDBOT. The label must be done while
# the filesystem is writable from the board side, then handed back to the host.
try:
    storage.remount("/", readonly=False)
    storage.getmount("/").label = "CLAWDBOT"
    storage.remount("/", readonly=True)
    print("relabel: OK -> CLAWDBOT")
except Exception as e:
    print("relabel FAILED:", repr(e))

try:
    # CircuitPython 8+ supports custom vid/pid here.
    supervisor.set_usb_identification(
        manufacturer="Clawd",
        product="Robot",
        vid=0x1209,        # pid.codes open-source vendor id
        pid=0x0001,
    )
except TypeError:
    # Older builds: name-only identification.
    supervisor.set_usb_identification(manufacturer="Clawd", product="Robot")
