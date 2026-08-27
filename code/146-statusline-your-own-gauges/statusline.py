#!/usr/bin/env python3
"""
statusline.py — the Workloft Claude Code statusline.

Claude Code pipes a JSON blob about the current session to this script's stdin
on every redraw; whatever we print to stdout becomes the bottom status bar. We
show two things: a dim context chunk (working dir + model) on the left, and one
rotating "gauge" from our own signal feed on the right. The feed is built out of
band by build-feed.py; here we just read the cache, pick a line by the clock,
and colour it. Fast and side-effect free: no network, no subprocess.

If the feed cache is missing we degrade to a plain context line, so a fresh
machine with the script installed but no cron yet still shows something sane.
"""

import json
import os
import sys
import time

FEED = os.path.expanduser("~/.workloft/statusline-feed.txt")

# Workloft accent #FA3E33 in truecolor; dim grey for context.
ACCENT = "\x1b[38;2;250;62;51m"
DIM = "\x1b[38;2;120;120;120m"
RESET = "\x1b[0m"


def read_context():
    """Pull dir basename + model name out of the CC status JSON, defensively."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        return None, None
    cwd = (data.get("workspace", {}).get("current_dir")
           or data.get("cwd") or "")
    directory = os.path.basename(cwd.rstrip("/")) if cwd else ""
    model = (data.get("model", {}) or {}).get("display_name") or ""
    return directory, model


def rotating_gauge():
    """One line from the feed, chosen by the minute so it changes as you wait."""
    try:
        with open(FEED, encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return None
    if not lines:
        return None
    idx = int(time.time() // 60) % len(lines)
    return lines[idx]


def main():
    directory, model = read_context()
    left_bits = [b for b in (directory, model) if b]
    left = f"{DIM}{' · '.join(left_bits)}{RESET}" if left_bits else ""

    gauge = rotating_gauge()
    if gauge:
        right = f"{ACCENT}◆{RESET} {gauge}"
        sep = f"  {DIM}│{RESET}  " if left else ""
        sys.stdout.write(left + sep + right)
    else:
        sys.stdout.write(left)


if __name__ == "__main__":
    main()
