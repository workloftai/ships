#!/usr/bin/env python3
"""
build-feed.py — refresh the Workloft statusline feed cache.

Reads local, already-owned signal (the Loop backlog via `gary list`, the latest
published Labs Note and Ship) and writes a handful of pre-rendered one-line
"gauges" to ~/.workloft/statusline-feed.txt. The statusline command rotates
through those lines, so this script does the slow work (parsing, file scans)
out of band — run it from cron every ~10 minutes, not on every prompt redraw.

No secrets, no network. If a source is missing it is skipped, never faked.
"""

import os
import re
import subprocess
import glob
import html
from datetime import datetime

HOME = os.path.expanduser("~")
OUT_DIR = os.path.join(HOME, ".workloft")
OUT_FILE = os.path.join(OUT_DIR, "statusline-feed.txt")

NOTES_DIR = os.path.join(HOME, "workloft-site", "labs", "notes")
SHIPS_DIR = os.path.join(HOME, "workloft-site", "ships")

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _truncate(text, width):
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _parse_due(due):
    """Turn a gary due tail like 'Thu 03 Sep 23:59' into a datetime, else None.

    'OVERDUE 67d', '—' (no date) and anything unparseable return None.
    """
    m = re.search(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{2}):(\d{2})", due)
    if not m:
        return None
    _, day, mon, hh, mm = m.groups()
    if mon not in MONTHS:
        return None
    now = datetime.now()
    try:
        dt = datetime(now.year, MONTHS[mon], int(day), int(hh), int(mm))
    except ValueError:
        return None
    # A month far in the past for "today" almost always means it rolled to next
    # year (e.g. it's December, the item is due January).
    if (dt - now).days < -180:
        dt = dt.replace(year=now.year + 1)
    return dt


def loop_lines():
    """Loop backlog pressure + the single next thing due, from `gary list`."""
    try:
        raw = subprocess.run(
            ["gary", "list", "--status", "open"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return []

    overdue = 0
    due_today = 0
    upcoming = []  # (datetime, title)
    today = datetime.now().date()

    for line in raw.splitlines():
        if "· due " not in line:
            continue
        head, due = line.split("· due ", 1)
        # strip id + priority glyph, keep the human title
        title = re.sub(r"^\s*[0-9a-f]{6,}\s*", "", head)
        title = re.sub(r"^[\U0001F300-\U0001FAFF☀-➿\s]+", "", title).strip()
        title = re.sub(r"\s*#\w+\s*$", "", title)
        due = due.strip()

        if "OVERDUE" in due:
            overdue += 1
            continue
        dt = _parse_due(due)
        if dt is None:
            continue
        if dt.date() == today:
            due_today += 1
        if dt >= datetime.now():
            upcoming.append((dt, title))

    lines = []
    if overdue or due_today:
        bits = []
        if overdue:
            bits.append(f"{overdue} overdue")
        if due_today:
            bits.append(f"{due_today} due today")
        lines.append("Loop: " + " · ".join(bits))
    if upcoming:
        upcoming.sort(key=lambda x: x[0])
        dt, title = upcoming[0]
        lines.append(f"Next: {_truncate(title, 46)} · {dt:%a %d %b}")
    return lines


def _latest_published(directory, label):
    """Newest dated <slug>-YYYY-MM-DD.html in a dir -> 'label: Title'."""
    files = [f for f in glob.glob(os.path.join(directory, "*.html"))
             if os.path.basename(f) != "index.html"]
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    try:
        with open(latest, encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        return None
    m = re.search(r"<title>(.*?)</title>", head, re.I | re.S)
    if m:
        title = html.unescape(m.group(1)).strip()
        # drop a trailing " | Workloft" style suffix
        title = re.split(r"\s*[|–—·]\s*Workloft", title)[0].strip()
    else:
        slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "",
                      os.path.basename(latest)[:-5])
        title = slug.replace("-", " ").capitalize()
    return f"{label}: {_truncate(title, 50)}"


def build():
    lines = []
    lines += loop_lines()
    for directory, label in ((SHIPS_DIR, "Latest ship"),
                             (NOTES_DIR, "Latest note")):
        item = _latest_published(directory, label)
        if item:
            lines.append(item)

    # Never write an empty feed: the statusline falls back cleanly, but a stale
    # non-empty cache is more useful than a blank one.
    if not lines:
        lines = ["Loop: clear"]

    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT_FILE)
    return lines


if __name__ == "__main__":
    for ln in build():
        print(ln)
