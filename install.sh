#!/bin/bash
# Claude Code servo notifier — host-side installer.
#
# Lives on the CIRCUITPY drive alongside servo_notify.py and README.md.
# Run with:  bash /Volumes/CIRCUITPY/install.sh
set -e

HOOK_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔─────────────────────────────────────╗"
echo "│   Claude Code Servo Notifier Setup  │"
echo "╚─────────────────────────────────────╝"
echo ""

echo "→ Checking dependencies..."
if ! command -v python3 &>/dev/null; then
    echo "  ✗ python3 not found. Install it from https://python.org"
    exit 1
fi
if ! python3 -c "import serial" &>/dev/null; then
    echo "  Installing pyserial..."
    pip3 install pyserial --quiet
fi
echo "  ✓ Dependencies OK"

echo "→ Installing hook script..."
mkdir -p "$HOOK_DIR"
cp "$SRC_DIR/servo_notify.py" "$HOOK_DIR/servo_notify.py"
chmod +x "$HOOK_DIR/servo_notify.py"
echo "  ✓ Installed to $HOOK_DIR/servo_notify.py"

echo "→ Registering Claude Code hooks (Stop/Notification -> raise, UserPromptSubmit -> lower)..."
mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

python3 - <<'PYEOF'
import json, pathlib

path = pathlib.Path.home() / ".claude/settings.json"
try:
    settings = json.loads(path.read_text())
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}

hooks = settings.setdefault("hooks", {})


def ensure(event, arg):
    cmd = "python3 ~/.claude/hooks/servo_notify.py " + arg
    entries = hooks.setdefault(event, [])
    already = any(
        any(h.get("command", "").startswith("python3 ~/.claude/hooks/servo_notify.py")
            for h in entry.get("hooks", []))
        for entry in entries
    )
    if already:
        print(f"  ✓ {event} hook already registered, skipping")
        return
    entries.append({"matcher": "", "hooks": [{"type": "command", "command": cmd}]})
    print(f"  ✓ {event} hook registered")


ensure("Stop", "up")
ensure("Notification", "up")        # Claude paused to ask a question / needs input
ensure("UserPromptSubmit", "think") # Claude started working -> pulse white
path.write_text(json.dumps(settings, indent=2))
PYEOF

echo ""
echo "✓ All done!"
echo "  • Servo raises to 180° when Claude Code finishes a task."
echo "  • Press the acknowledge button on GP0 (or send your next prompt) to lower it."
echo ""
echo "  To uninstall:"
echo "    rm ~/.claude/hooks/servo_notify.py"
echo "    # and remove the Stop + UserPromptSubmit servo entries from ~/.claude/settings.json"
