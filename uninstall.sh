#!/bin/bash
# Claude Code servo notifier — host-side uninstaller.
#
# Reverses install.sh: removes the servo hook entries from ~/.claude/settings.json
# and removes the installed hook script, its venv, and the state/log files.
# Run with:  bash /Volumes/CLAWDBOT/uninstall.sh
#
# Does NOT touch the board itself (code.py / boot.py live on the CIRCUITPY drive).
set -e

HOOK_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

echo "╔─────────────────────────────────────╗"
echo "│  Claude Code Servo Notifier Removal │"
echo "╚─────────────────────────────────────╝"
echo ""

# Recoverable removal: prefer the `trash` CLI, otherwise move into ~/.Trash with a
# timestamp so nothing is irreversibly deleted.
trash_path() {
    target="$1"
    [ -e "$target" ] || return 0
    if command -v trash &>/dev/null; then
        trash "$target"
    else
        mkdir -p "$HOME/.Trash"
        mv "$target" "$HOME/.Trash/$(basename "$target").$(date +%Y%m%d-%H%M%S)"
    fi
    echo "  ✓ removed $target"
}

echo "→ Removing servo hook entries from settings.json..."
if [ -f "$SETTINGS" ]; then
    # Back up the current settings into ~/.Trash before rewriting it.
    mkdir -p "$HOME/.Trash"
    cp "$SETTINGS" "$HOME/.Trash/settings.json.$(date +%Y%m%d-%H%M%S).bak"

    python3 - <<'PYEOF'
import json
import pathlib

path = pathlib.Path.home() / ".claude/settings.json"
try:
    settings = json.loads(path.read_text())
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}

hooks = settings.get("hooks", {})
removed = 0
# Walk every event (not just the four we register) and drop any hook whose command
# runs servo_notify.py, then prune entries/events left empty by the removal.
for event in list(hooks.keys()):
    kept_entries = []
    for entry in hooks.get(event, []):
        original = entry.get("hooks", [])
        kept = [h for h in original if "servo_notify.py" not in h.get("command", "")]
        removed += len(original) - len(kept)
        if kept:
            entry["hooks"] = kept
            kept_entries.append(entry)
        # an entry left with no hooks held only the servo command -> drop it
    if kept_entries:
        hooks[event] = kept_entries
    else:
        del hooks[event]            # the event held only servo hooks

if not hooks:
    settings.pop("hooks", None)     # no hooks left at all

path.write_text(json.dumps(settings, indent=2))
print(f"  ✓ removed {removed} servo hook " + ("entry" if removed == 1 else "entries"))
PYEOF
else
    echo "  • no settings.json found, skipping"
fi

echo "→ Removing installed files..."
trash_path "$HOOK_DIR/servo_notify.py"
trash_path "$HOOK_DIR/.venv"
trash_path "$HOOK_DIR/.servo_state"
trash_path "$HOOK_DIR/servo_notify.log"   # diagnostic log, if present

echo ""
echo "✓ Uninstalled. The servo flag will no longer respond to Claude Code."
echo "  Settings backed up to ~/.Trash/ before editing; removed files are in the Trash."
echo "  (The board's own firmware on the CIRCUITPY drive is untouched.)"
