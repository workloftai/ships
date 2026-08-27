# Workloft statusline

Claude Code runs a command every time it redraws, and prints whatever that
command returns as the status bar at the bottom of your terminal. Most people
leave it showing the model name and current directory. That bar is dead space
while an agent is off doing a long tool call.

This fills it with **your** signal instead: how much is overdue on your backlog,
what's due next, and what you last shipped. One gauge at a time, rotating once a
minute, so glancing down tells you something you'd otherwise have to go and
check.

It reads only local sources you already own. No network, no secrets, no
telemetry. If a source is missing it's skipped, never faked.

## Two moving parts

- **`statusline.py`** — the command Claude Code calls on every redraw. It parses
  the session JSON on stdin (working dir + model), reads the pre-built feed
  cache, picks one line by the clock, colours it, and prints. Fast: no
  subprocess, no network, so it never slows the prompt.
- **`build-feed.py`** — the slow half, run on cron every ~10 minutes. It parses
  the backlog (`gary list`) and scans the latest published ship and note, then
  writes a handful of one-line gauges to `~/.workloft/statusline-feed.txt`.

Splitting the two matters: the redraw path stays instant while the parsing
happens out of band.

## Install

1. Point Claude Code at the statusline in `~/.claude/settings.json`:

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "/absolute/path/to/statusline.py"
     }
   }
   ```

2. Refresh the feed on a schedule (crontab -e):

   ```cron
   */10 * * * * cd $HOME/workloft-statusline && /usr/bin/python3 build-feed.py >/dev/null 2>&1
   ```

3. Run `./demo.sh` to see it before you commit.

## Make it yours

The feed is the interesting bit, and it's ~40 lines. `build-feed.py` returns a
list of short strings; swap the sources for whatever your day runs on: open PRs,
failing CI, an on-call queue, unread from a label, deploy status. The one rule
is keep each gauge to one short line and keep the builder cheap, because cron
runs it whether you're looking or not.

The signal is the point. The colours are just paint.

## Licence

MIT.
