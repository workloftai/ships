#!/usr/bin/env python3
"""Tests for the Workloft statusline. Run: python3 test_statusline.py"""

import importlib.util
import io
import os
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

feed = _load("build-feed")
sl = _load("statusline")

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


# --- build-feed date parsing -------------------------------------------------
now = datetime.now()
good = f"{now:%a} {now.day:02d} {now:%b} 09:30"
check("parse_due reads a real gary date", feed._parse_due(good) is not None)
check("parse_due rejects OVERDUE tail", feed._parse_due("OVERDUE 67d") is None)
check("parse_due rejects no-date dash", feed._parse_due("—") is None)
check("truncate adds ellipsis over width",
      feed._truncate("x" * 80, 20).endswith("…") and len(feed._truncate("x" * 80, 20)) == 20)
check("truncate leaves short text",
      feed._truncate("short", 20) == "short")

# --- statusline rotation -----------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    fp = os.path.join(d, "feed.txt")
    with open(fp, "w") as fh:
        fh.write("A\nB\nC\n")
    sl.FEED = fp
    seen = set()
    real_time = sl.time.time
    try:
        for minute in range(3):
            sl.time.time = (lambda m: (lambda: m * 60))(minute)
            seen.add(sl.rotating_gauge())
    finally:
        sl.time.time = real_time
    check("rotation cycles through every feed line", seen == {"A", "B", "C"})

# missing feed -> None, not a crash
sl.FEED = "/nonexistent/feed.txt"
check("missing feed returns None", sl.rotating_gauge() is None)

# --- context parsing ---------------------------------------------------------
sys.stdin = io.StringIO(
    '{"workspace":{"current_dir":"/home/workloft/conexus"},'
    '"model":{"display_name":"Opus 4.8"}}')
directory, model = sl.read_context()
check("context reads dir basename", directory == "conexus")
check("context reads model name", model == "Opus 4.8")

sys.stdin = io.StringIO("not json")
d2, m2 = sl.read_context()
check("bad json degrades to blanks", d2 is None and m2 is None)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
