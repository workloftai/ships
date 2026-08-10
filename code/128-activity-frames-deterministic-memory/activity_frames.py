"""
activity_frames.py — deterministic screen-activity compilation for agent memory.

A zero-model reimplementation of the core idea in "Activity Frames: Deterministic
Screen-Activity Compilation for Agent Memory and Replay" (arXiv:2608.05784).

The problem: a day of raw screen capture is thousands of tiny rows (focus changes,
keystroke bursts, clicks, scrolls). Feeding that to an agent is expensive and noisy.
The paper's move is to compile the raw stream into a handful of *typed activity
frames* with a deterministic, no-model pipeline: byte-identical output, cacheable,
mechanically auditable, ~86x smaller, and replayable with the model out of the loop.

This file is that pipeline in one dependency-free module:
  - RawEvent / ActivityFrame dataclasses
  - compile_frames()  — deterministic segmentation + aggregation + typing
  - answer()          — deterministic Q&A over frames (the eval surface)
  - detect_routines() — recurrent frame-signature n-grams across days
  - replay()          — re-emit a routine with zero model tokens

Determinism contract: same input rows -> byte-identical frames JSON. No wall-clock,
no randomness, no floats that vary by platform. Verified by test_activity_frames.py.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Iterable

# ---------------------------------------------------------------------------
# Segmentation parameters. These are the ONLY knobs; changing them changes the
# compilation deterministically. Documented so an auditor can reason about cuts.
# ---------------------------------------------------------------------------
IDLE_GAP_S = 90          # a gap with no input longer than this starts a new frame
MAX_FRAME_S = 1800       # hard cap: no frame spans more than 30 min
MIN_FRAME_S = 2          # frames shorter than this fold into "idle" typing

# Deterministic app/site -> activity type lookup. First match wins, top to bottom.
# Kept as ordered rules so the mapping is auditable, not a learned classifier.
TYPE_RULES = (
    ("communication", {"slack", "gmail", "outlook", "telegram", "discord", "zoom"}),
    ("coding",        {"vscode", "terminal", "iterm", "pycharm", "intellij", "vim"}),
    ("browsing_docs", {"github.com", "stackoverflow.com", "docs.python.org", "arxiv.org"}),
    ("browsing_web",  {"chrome", "safari", "firefox", "google.com"}),
    ("writing",       {"notion", "word", "docs.google.com", "obsidian"}),
    ("design",        {"figma", "photoshop", "canva"}),
)


@dataclass(frozen=True)
class RawEvent:
    """One row of a local capture stream. `ts` is integer seconds (epoch-relative)."""
    ts: int
    app: str
    site: str            # domain for browsers, "" otherwise
    window: str          # window / tab title
    keystrokes: int = 0
    clicks: int = 0
    scrolls: int = 0


@dataclass
class ActivityFrame:
    """A bounded episode of activity. Aggregates many RawEvents into one typed unit."""
    frame_id: int
    type: str
    app: str
    site: str
    start_ts: int
    end_ts: int
    duration_s: int
    keystrokes: int
    clicks: int
    scrolls: int
    title: str                       # representative window title (first seen)
    # Evidence as compact contiguous [start, end] ranges into the raw stream, so a
    # frame stays O(1)-ish in size while remaining mechanically auditable: to check
    # a frame you re-read exactly those raw rows. Storing every index would defeat
    # the whole point (compression), so we collapse runs of consecutive indices.
    evidence: list = field(default_factory=list)   # e.g. [[0, 899], [905, 910]]

    def signature(self) -> str:
        """Stable identity for routine detection: what the frame IS, not when."""
        return f"{self.type}:{self.app}:{self.site}"


def _classify(app: str, site: str) -> str:
    """Deterministic type from app/site. Ordered rules, first match wins."""
    app_l, site_l = app.lower(), site.lower()
    for label, keys in TYPE_RULES:
        if app_l in keys or (site_l and site_l in keys):
            return label
    return "other"


def _boundary(prev: RawEvent, cur: RawEvent, frame_start: int) -> bool:
    """True if `cur` must start a new frame relative to the current run."""
    if cur.app != prev.app:
        return True
    if cur.site != prev.site:
        return True
    if cur.ts - prev.ts > IDLE_GAP_S:
        return True
    if cur.ts - frame_start >= MAX_FRAME_S:
        return True
    return False


def _ranges(idxs: list[int]) -> list[list[int]]:
    """Collapse a list of ints into compact contiguous [start, end] ranges."""
    if not idxs:
        return []
    s = sorted(idxs)
    out = [[s[0], s[0]]]
    for i in s[1:]:
        if i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def compile_frames(events: Iterable[RawEvent]) -> list[ActivityFrame]:
    """Segment a raw capture stream into typed activity frames. Deterministic."""
    events = list(events)
    if not events:
        return []
    # Stable sort by timestamp; ties keep input order so output is reproducible.
    order = sorted(range(len(events)), key=lambda i: (events[i].ts, i))

    frames: list[ActivityFrame] = []
    run: list[int] = [order[0]]
    frame_start = events[order[0]].ts

    def flush(idxs: list[int]) -> None:
        rows = [events[i] for i in idxs]
        first, last = rows[0], rows[-1]
        # +1: each row is one sampled second, so a run from t..t+n-1 covers n seconds.
        dur = last.ts - first.ts + 1
        f = ActivityFrame(
            frame_id=len(frames),
            type=_classify(first.app, first.site),
            app=first.app,
            site=first.site,
            start_ts=first.ts,
            end_ts=last.ts,
            duration_s=dur,
            keystrokes=sum(r.keystrokes for r in rows),
            clicks=sum(r.clicks for r in rows),
            scrolls=sum(r.scrolls for r in rows),
            title=first.window,
            evidence=_ranges(idxs),
        )
        if dur < MIN_FRAME_S and f.keystrokes == 0 and f.clicks == 0:
            f.type = "idle"
        frames.append(f)

    for pos in order[1:]:
        prev = events[run[-1]]
        cur = events[pos]
        if _boundary(prev, cur, frame_start):
            flush(run)
            run = [pos]
            frame_start = cur.ts
        else:
            run.append(pos)
    flush(run)
    return frames


def frames_to_json(frames: list[ActivityFrame]) -> str:
    """Canonical, byte-identical serialization. sort_keys => cacheable by hash."""
    return json.dumps([asdict(f) for f in frames], sort_keys=True, separators=(",", ":"))


def content_hash(frames: list[ActivityFrame]) -> str:
    return hashlib.sha256(frames_to_json(frames).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Deterministic Q&A — the eval surface. The paper answers questions about
# captured activity from frames alone (no model). These are exact aggregations.
# ---------------------------------------------------------------------------
def answer(frames: list[ActivityFrame], question: str) -> str:
    """Answer a small set of structured questions deterministically from frames."""
    q = question.lower().strip()

    if "how long" in q or "time on" in q or "minutes on" in q:
        # "how long on <app/type>?"
        target = q.split(" on ")[-1].strip(" ?")
        secs = sum(f.duration_s for f in frames
                   if target in (f.app.lower(), f.type.lower(), f.site.lower()))
        return f"{secs // 60}m {secs % 60}s"

    if "most keystrokes" in q or "most typing" in q:
        if not frames:
            return "none"
        f = max(frames, key=lambda x: x.keystrokes)
        return f"{f.app or f.site} ({f.keystrokes} keystrokes)"

    if "how many frames" in q or "number of frames" in q:
        return str(len(frames))

    if "what was i doing at" in q or "at time" in q:
        # "... at time <ts>"
        try:
            t = int("".join(ch for ch in q.split("at")[-1] if ch.isdigit()))
        except ValueError:
            return "unparseable timestamp"
        for f in frames:
            if f.start_ts <= t <= f.end_ts:
                return f"{f.type} in {f.app or f.site} ('{f.title}')"
        return "no activity captured at that time"

    if "which apps" in q or "list apps" in q:
        apps = sorted({f.app for f in frames if f.app})
        return ", ".join(apps) if apps else "none"

    return "unsupported question"


# ---------------------------------------------------------------------------
# Routine detection + replay. A routine is a frame-signature n-gram that recurs
# across days. Replay re-emits it with the model out of the loop (zero tokens).
# ---------------------------------------------------------------------------
def detect_routines(days: list[list[ActivityFrame]], n: int = 3, min_days: int = 2) -> list[dict]:
    """Find signature n-grams that appear on >= min_days distinct days."""
    seen: dict[tuple, set] = {}
    for day_idx, day in enumerate(days):
        sigs = [f.signature() for f in day]
        for i in range(len(sigs) - n + 1):
            gram = tuple(sigs[i:i + n])
            seen.setdefault(gram, set()).add(day_idx)
    routines = [
        {"routine": list(gram), "days_seen": sorted(d), "recurrence": len(d)}
        for gram, d in seen.items() if len(d) >= min_days
    ]
    # Deterministic order: most recurrent first, then lexical.
    routines.sort(key=lambda r: (-r["recurrence"], r["routine"]))
    return routines


def replay(routine: dict) -> list[str]:
    """Deterministically re-emit a routine's steps. No model, zero tokens."""
    return [f"step {i+1}: open {sig.split(':')[1] or sig.split(':')[2]} "
            f"({sig.split(':')[0]})"
            for i, sig in enumerate(routine["routine"])]
