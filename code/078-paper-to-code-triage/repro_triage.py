#!/usr/bin/env python3
"""
repro_triage.py — the cheap gate we put in front of "implement this paper".

Context
-------
Tools like alphaXiv's autoarxiv now do the boring 80% of paper reproduction:
fix the repo's setup, run a minimal reproduction, estimate the full replication
cost. They are genuinely useful, but they are hosted behind a login, so you
cannot wire one into an automated pipeline as a stage. And reproduction is not
implementation: "the code ran" is not "the result matched" and is not "this is
worth building on".

So before any human (or agent) spends real time hand-implementing a paper, we
run this triage gate. It scores the *cheap, static* signals that decide whether
a full build is even worth probing, and recommends one of four actions. It does
NOT claim the paper reproduces — that needs execution, which is the next stage,
not this one.

Signals (all cheap, all static — no execution)
----------------------------------------------
  1. official_code   Is there an official code repo at all? (no repo => no build)
  2. env_pinned      Is the environment pinned? (requirements/lock/pyproject/env.yml)
  3. runnable_entry  Is there an obvious entrypoint or test? (README run cmd, tests/, *.py main)
  4. weight          How heavy is full replication likely to be? (repo size as a rough proxy)

Bands -> action
---------------
  BUILD  signals 1-3 all present, weight light/medium  -> worth a hand-build
  PROBE  1-3 present, weight heavy                      -> run a minimal repro first (this is exactly autoarxiv's job)
  PARK   code exists but env or entry missing           -> needs setup archaeology; only if it matters to the stack
  KILL   no official code                               -> do not hand-build from prose alone

Usage
-----
  python3 repro_triage.py owner/repo          # live check via the GitHub API (anonymous)
  python3 repro_triage.py --demo              # run against bundled fixtures, no network

This is deliberately small and dependency-free (standard library only) so it can
be a real Loop stage, not a manual login.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

GH_API = "https://api.github.com"

ENV_FILES = (
    "requirements.txt", "requirements-dev.txt", "environment.yml", "environment.yaml",
    "pyproject.toml", "poetry.lock", "Pipfile", "Pipfile.lock", "conda.yaml",
    "setup.py", "setup.cfg", "uv.lock",
)
ENTRY_HINTS = ("train.py", "main.py", "run.py", "eval.py", "demo.py", "reproduce.py")


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "workloft-repro-triage"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def probe_repo(slug: str) -> dict:
    """Fetch the four cheap signals for a GitHub repo `owner/name`."""
    meta = _get(f"{GH_API}/repos/{slug}")
    tree = _get(f"{GH_API}/repos/{slug}/git/trees/{meta['default_branch']}?recursive=1")
    paths = [n["path"] for n in tree.get("tree", []) if n["type"] == "blob"]
    lower = {p.lower() for p in paths}
    basenames = {p.rsplit("/", 1)[-1].lower() for p in paths}

    env_pinned = any(f in basenames for f in ENV_FILES)
    has_tests = any(p.startswith("test") or "/test" in p for p in lower)
    has_entry = any(b in ENTRY_HINTS for b in basenames)
    has_readme = any(b.startswith("readme") for b in basenames)

    return {
        "slug": slug,
        "official_code": True,  # we got here, so a repo exists
        "env_pinned": env_pinned,
        "runnable_entry": bool(has_entry or has_tests),
        "kb": meta.get("size", 0),  # repo size in KB, GitHub's own number
        "stars": meta.get("stargazers_count", 0),
        "_detail": {
            "env_pinned": env_pinned,
            "has_entry": has_entry,
            "has_tests": has_tests,
            "has_readme": has_readme,
        },
    }


def band(sig: dict) -> tuple[str, str]:
    """Map signals to (action, one-line reason). Pure function, easy to test."""
    if not sig["official_code"]:
        return "KILL", "no official code; do not hand-build from the prose alone"
    if not (sig["env_pinned"] and sig["runnable_entry"]):
        missing = []
        if not sig["env_pinned"]:
            missing.append("no pinned environment")
        if not sig["runnable_entry"]:
            missing.append("no obvious entrypoint or tests")
        return "PARK", "code exists but " + " and ".join(missing) + "; setup archaeology first"
    heavy = sig["kb"] > 250_000  # >~250 MB checked-in: likely bundled weights/data
    if heavy:
        return "PROBE", "complete repo but heavy; run a minimal reproduction before any full build"
    return "BUILD", "official code, pinned env, runnable entrypoint, light enough; worth a hand-build"


MARKS = {"BUILD": "✅", "PROBE": "🟠", "PARK": "🟡", "KILL": "⛔"}


def report(sig: dict) -> str:
    action, reason = band(sig)
    flags = "  ".join(
        f"{k}={'y' if sig[k] else 'n'}" for k in ("official_code", "env_pinned", "runnable_entry")
    )
    size_mb = sig["kb"] / 1024
    return (
        f"{MARKS[action]} {action:5}  {sig['slug']}\n"
        f"          {flags}  size={size_mb:.0f}MB  stars={sig.get('stars', 0)}\n"
        f"          -> {reason}"
    )


# Fixtures for --demo: shapes only, so the gate logic is visible without a network.
DEMO = [
    {"slug": "demo/clean-benchmark", "official_code": True, "env_pinned": True,
     "runnable_entry": True, "kb": 4_200, "stars": 310},
    {"slug": "demo/heavy-weights-bundled", "official_code": True, "env_pinned": True,
     "runnable_entry": True, "kb": 900_000, "stars": 1_240},
    {"slug": "demo/notebook-only", "official_code": True, "env_pinned": False,
     "runnable_entry": True, "kb": 2_100, "stars": 58},
    {"slug": "demo/paper-no-repo", "official_code": False, "env_pinned": False,
     "runnable_entry": False, "kb": 0, "stars": 0},
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Cheap triage gate before implementing a paper.")
    ap.add_argument("repo", nargs="?", help="GitHub repo as owner/name")
    ap.add_argument("--demo", action="store_true", help="run against bundled fixtures, no network")
    args = ap.parse_args()

    if args.demo:
        print("repro-triage demo — gate logic on four fixture repos:\n")
        for sig in DEMO:
            print(report(sig), "\n")
        return 0

    if not args.repo:
        ap.error("give a repo as owner/name, or pass --demo")

    try:
        sig = probe_repo(args.repo)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(report({"slug": args.repo, "official_code": False, "env_pinned": False,
                          "runnable_entry": False, "kb": 0, "stars": 0}))
            return 0
        print(f"github api error {e.code}: {e.reason}", file=sys.stderr)
        return 2
    print(report(sig))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
