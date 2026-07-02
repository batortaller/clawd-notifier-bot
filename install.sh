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

# Use an isolated venv so we never touch an "externally managed" (PEP 668)
# system/Homebrew Python, and so the hook always has a deterministic interpreter.
VENV_DIR="$HOOK_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
mkdir -p "$HOOK_DIR"
[ -x "$VENV_PY" ] || python3 -m venv "$VENV_DIR"
if ! "$VENV_PY" -c "import serial" &>/dev/null; then
    echo "  Installing pyserial into venv..."
    "$VENV_PY" -m pip install pyserial --quiet
fi
echo "  ✓ Dependencies OK ($VENV_DIR)"

echo "→ Installing hook script..."
mkdir -p "$HOOK_DIR"
cp "$SRC_DIR/servo_notify.py" "$HOOK_DIR/servo_notify.py"
chmod +x "$HOOK_DIR/servo_notify.py"
echo "  ✓ Installed to $HOOK_DIR/servo_notify.py"

echo "→ Registering Claude Code hooks (Stop + Notification -> raise, UserPromptSubmit + PostToolUse -> lower)..."
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


def ensure(event, arg, matcher=""):
    cmd = "~/.claude/hooks/.venv/bin/python ~/.claude/hooks/servo_notify.py " + arg
    entries = hooks.setdefault(event, [])
    found = False
    for entry in entries:
        for h in entry.get("hooks", []):
            if "servo_notify.py" in h.get("command", ""):
                found = True
                # Upgrade stale entries in place: command (e.g. bare python3) and
                # matcher (empty "" never matched permission_prompt notifications).
                if h["command"] != cmd or entry.get("matcher", "") != matcher:
                    h["command"] = cmd
                    entry["matcher"] = matcher
                    print(f"  ✓ {event} hook updated")
                else:
                    print(f"  ✓ {event} hook already registered, skipping")
    if found:
        return
    entries.append({"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]})
    print(f"  ✓ {event} hook registered")


ensure("Stop", "up")            # Claude finished a task
# Empty matcher = all notification types. NOTE: Claude Code only emits a
# Notification event when it actually surfaces one (terminal CLI). The VSCode
# extension handles permission prompts in-IDE and does NOT fire this hook, so the
# flag will not rise on permission requests there. See README/CHANGELOG.
ensure("Notification", "up")    # Claude needs permission / is asking the user
ensure("UserPromptSubmit", "down")  # next prompt sent
ensure("PostToolUse", "down")   # approved action ran -> drop the flag
path.write_text(json.dumps(settings, indent=2))
PYEOF

echo ""
echo "✓ All done!"
echo "  • Servo raises to 180° when Claude Code finishes a task,"
echo "    needs permission, or is asking you a question."
echo "  • It lowers when the approved action completes or you send your next prompt"
echo "    (or press the acknowledge button on GP0)."
echo "  • Multiple pending requests are counted: clearing one while others remain"
echo "    dips the arm and raises it again to signal there's still something waiting."
echo ""
echo "  To uninstall:"
echo "    bash \"$SRC_DIR/uninstall.sh\""
