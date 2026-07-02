# Clawd Notifier Bot

A little servo flag + onboard LED that shows what Claude Code is doing.

- **Flag UP + solid white LED** — Claude finished, or needs your input.
- **Flag DOWN + pulsing white** — Claude is working / thinking.
- **Flag DOWN + LED off** — idle / acknowledged.

Button (wired `GP0` → button → `GND`):

- **Press once** — lower the flag ("I saw it").
- **Triple-press within 2 s** — make the arm dance. 🎉

## Setup

1. Plug the board into USB.
2. Install the Claude Code hook:
   ```bash
   bash install.sh
   ```
3. That's it — finish a task and watch the flag go up.

Full docs & source: https://github.com/batortaller/clawd-notifier-bot
