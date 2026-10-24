#!/usr/bin/env python3
"""Example status-band feed: git state of the current directory, no dependencies."""
import json
import subprocess


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


branch = git("rev-parse", "--abbrev-ref", "HEAD") or "no repo"
dirty = len([l for l in git("status", "--porcelain").splitlines() if l])
ahead = git("rev-list", "--count", "@{u}..HEAD")
ahead = int(ahead) if ahead.isdigit() else 0

print(json.dumps({
    "title": branch,
    "segments": [
        {"label": "uncommitted", "value": dirty, "alert": dirty > 20},
        {"label": "unpushed", "value": ahead, "alert": ahead > 0},
    ],
    "detail": git("status", "--short", "--branch") or "Not a git repository.",
}))
