"""
demo.py — generate a synthetic day of raw screen capture, compile it into Activity
Frames, and report the three numbers the paper cares about:
  1. compression ratio (raw bytes -> frame bytes)
  2. deterministic Q&A accuracy vs ground truth (paper: 98.4%)
  3. a routine detected across days, replayed at zero model tokens

No dependencies, no randomness (a fixed LCG so the "day" is reproducible), no model.
Run: python3 demo.py
"""

from __future__ import annotations

import json
from activity_frames import (
    RawEvent, compile_frames, frames_to_json, content_hash,
    answer, detect_routines, replay,
)


class LCG:
    """Tiny deterministic PRNG so demo data is byte-identical every run."""
    def __init__(self, seed: int) -> None:
        self.s = seed
    def nxt(self, mod: int) -> int:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s % mod


# A realistic weekday: blocks of app usage with per-second capture rows. This is
# what a screen recorder emits — one row per second of activity, noisy and huge.
BLOCKS = [
    ("slack",    "",                 "Slack — general",        120, 3, 1, 0),
    ("vscode",   "",                 "activity_frames.py",     900, 8, 0, 0),
    ("terminal", "",                 "zsh — pytest",           180, 5, 0, 0),
    ("chrome",   "github.com",       "PR #128",                240, 2, 3, 4),
    ("chrome",   "stackoverflow.com","dataclass frozen",       160, 1, 1, 6),
    ("gmail",    "",                 "Inbox (3)",              140, 4, 2, 0),
    ("vscode",   "",                 "test_activity_frames.py",600, 7, 0, 0),
    ("notion",   "",                 "Ship #128 notes",        200, 6, 1, 1),
    ("slack",    "",                 "Slack — dev",            110, 3, 1, 0),
]


def gen_day(seed: int, start: int = 0, cycles: int = 6) -> tuple[list[RawEvent], dict]:
    """Emit one row per active second across the blocks, repeated `cycles` times to
    span a realistic workday. Returns (rows, ground_truth)."""
    rng = LCG(seed)
    rows: list[RawEvent] = []
    t = start
    truth_secs: dict[str, int] = {}
    truth_keys: dict[str, int] = {}
    schedule = BLOCKS * cycles
    for bi, (app, site, title, dur, kpm, cpm, spm) in enumerate(schedule):
        truth_secs[app] = truth_secs.get(app, 0)
        for _ in range(dur):
            k = 1 if rng.nxt(60) < kpm else 0
            c = 1 if rng.nxt(60) < cpm else 0
            s = 1 if rng.nxt(60) < spm else 0
            rows.append(RawEvent(t, app, site, title, k, c, s))
            truth_keys[app] = truth_keys.get(app, 0) + k
            t += 1
        truth_secs[app] += dur
        # Only insert an idle gap when the NEXT block is a different app. Continuous
        # same-app work has no gap, so a frame's wall-clock duration == active seconds
        # and the deterministic Q&A can be checked exactly against ground truth.
        nxt = schedule[bi + 1] if bi + 1 < len(schedule) else None
        if nxt and nxt[0] != app:
            t += 30
    return rows, {"secs": truth_secs, "keys": truth_keys, "end": t}


def main() -> None:
    rows, truth = gen_day(seed=42)
    frames = compile_frames(rows)

    raw_bytes = len(json.dumps([r.__dict__ for r in rows], separators=(",", ":")).encode())
    frame_bytes = len(frames_to_json(frames).encode())
    ratio = raw_bytes / frame_bytes

    print("=" * 64)
    print("ACTIVITY FRAMES — deterministic screen-activity compilation")
    print("=" * 64)
    print(f"raw capture rows      : {len(rows)}")
    print(f"compiled frames       : {len(frames)}")
    print(f"raw bytes             : {raw_bytes:,}")
    print(f"frame bytes           : {frame_bytes:,}")
    print(f"COMPRESSION RATIO     : {ratio:.1f}x")
    print(f"content hash (cache)  : {content_hash(frames)[:16]}…")

    # Determinism proof: recompile, hashes must match byte-for-byte.
    assert content_hash(frames) == content_hash(compile_frames(rows)), "non-deterministic!"
    print("determinism           : PASS (byte-identical recompile)")

    # ---- Q&A accuracy vs ground truth -------------------------------------
    print("\n--- deterministic Q&A vs ground truth ---")
    checks = []
    for app in ["vscode", "slack", "gmail", "terminal"]:
        got = answer(frames, f"how long on {app}?")
        exp_s = truth["secs"][app]
        exp = f"{exp_s // 60}m {exp_s % 60}s"
        ok = got == exp
        checks.append(ok)
        print(f"  how long on {app:9}: {got:>10}  (truth {exp:>10})  {'OK' if ok else 'X'}")

    # most-keystrokes check
    exp_app = max(truth["keys"], key=truth["keys"].get)
    got = answer(frames, "which app had the most keystrokes?")
    ok = exp_app in got
    checks.append(ok)
    print(f"  most keystrokes      : {got}  (truth {exp_app})  {'OK' if ok else 'X'}")

    # point-in-time check
    got = answer(frames, "what was i doing at time 50?")
    ok = "slack" in got.lower()
    checks.append(ok)
    print(f"  activity @ t=50      : {got}  {'OK' if ok else 'X'}")

    acc = 100.0 * sum(checks) / len(checks)
    print(f"\nQ&A ACCURACY          : {acc:.1f}%  ({sum(checks)}/{len(checks)})")

    # ---- routine detection + zero-token replay ----------------------------
    print("\n--- routine detection across 3 days ---")
    days = []
    start = 0
    for d in range(3):
        r, tr = gen_day(seed=42, start=start)  # same routine each day
        days.append(compile_frames(r))
        start = tr["end"] + 3600
    routines = detect_routines(days, n=3, min_days=2)
    print(f"recurrent routines    : {len(routines)}")
    top = routines[0]
    print(f"top routine (seen {top['recurrence']}/3 days):")
    for step in replay(top):
        print(f"    {step}")
    print("replay cost           : 0 model tokens")
    print("=" * 64)

    all_ok = all(checks) and len(frames) < len(rows) and len(routines) > 0
    print("RESULT:", "ALL CHECKS PASS" if all_ok else "FAILURE")
    return all_ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
