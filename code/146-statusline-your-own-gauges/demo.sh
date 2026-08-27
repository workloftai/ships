#!/usr/bin/env bash
# demo.sh — show the Workloft statusline without wiring it into Claude Code.
# Builds the feed, then renders one frame per feed line so you can see the
# rotation the way it would appear at the bottom of your terminal.
set -euo pipefail
cd "$(dirname "$0")"

echo "Building feed from local signal (Loop + latest ship/note)..."
python3 build-feed.py >/dev/null
echo "Each gauge shows one at a time, rotating once a minute:"
echo

python3 - <<'PY'
import io, importlib.util
spec = importlib.util.spec_from_file_location("sl", "statusline.py")
sl = importlib.util.module_from_spec(spec); spec.loader.exec_module(sl)

with open(sl.FEED, encoding="utf-8") as fh:
    n = len([ln for ln in fh if ln.strip()])

ctx = ('{"workspace":{"current_dir":"/home/workloft/conexus"},'
       '"model":{"display_name":"Opus 4.8"}}')
import sys
for minute in range(n):
    sl.time.time = (lambda m: (lambda: m * 60))(minute)  # pin the clock
    sys.stdin = io.StringIO(ctx)
    sys.stdout.write("  ")
    sl.main()
    sys.stdout.write("\n")
PY

echo
echo "Wire it in: add statusLine to ~/.claude/settings.json (see README) and"
echo "schedule build-feed.py on cron every ~10 min. That's it."
