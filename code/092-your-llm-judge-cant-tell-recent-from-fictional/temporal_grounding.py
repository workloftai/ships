"""Temporal grounding for an LLM-as-judge.

An LLM used as a judge/grader/reviewer has no reliable sense of what day it is.
Show it a candidate that references an event, release or version newer than its
training data and it cannot tell "recent and real" from "fictional", so a
kill-biased judge rejects it and calls the date hypothetical. That silently
poisons any evaluation of fresh input (news, current events, new library
versions).

The fix is a few lines of prompt: state today's real date and forbid "it
postdates what I know" as a reason to reject. This module is the standalone,
dependency-free version of what we wired into our own three-juror panel.

Usage:
    from temporal_grounding import ground

    system_prompt = ground(YOUR_JUDGE_SYSTEM_PROMPT)          # uses today
    system_prompt = ground(YOUR_JUDGE_SYSTEM_PROMPT, today="2026-07-01")

Then send `system_prompt` as the judge's system message as usual. Nothing else
changes: it is inert on candidates that never mention a date, and it works
whether your judge is strict or lenient.
"""
from __future__ import annotations

import datetime
import os

# The grounding preamble. {today} is filled at call time. Keep this TEMPLATE
# (with the placeholder unresolved) as the thing you hash if you fingerprint
# your prompts for drift, so the daily date value does not look like a change.
TEMPORAL_ANCHOR_TEMPLATE = """TEMPORAL GROUNDING - READ FIRST.
Today's real date is {today}. You are being run on that date; your training cut-off is earlier, so any event, release, model, version or date in the candidate that looks "future" to you may simply be RECENT and REAL. Do NOT reject, and do NOT dock confidence, on the sole ground that something "does not exist yet", "is in the future", or "is fictional/hypothetical/speculative": any date on or before {today} is a real point in the past or present. Judge the SUBSTANCE against the criteria. You may still reject a specific claim you can independently show is wrong on NON-temporal grounds, but "it postdates what I know" is not evidence and is never a valid reason to reject.

"""


def today_iso(today: str | None = None) -> str:
    """Resolve today's date as ISO YYYY-MM-DD.

    Precedence: explicit arg > JUDGE_TODAY env var (handy for deterministic
    tests, or to pin the clock a calling system already knows) > system clock.
    """
    return (today or os.environ.get("JUDGE_TODAY") or
            datetime.date.today().isoformat())


def anchor(today: str | None = None) -> str:
    """The resolved grounding preamble for the given (or current) date."""
    return TEMPORAL_ANCHOR_TEMPLATE.format(today=today_iso(today))


def ground(system_prompt: str, today: str | None = None) -> str:
    """Prepend the grounding preamble to a judge system prompt."""
    return anchor(today) + system_prompt


if __name__ == "__main__":
    demo = ground("You are a strict reviewer. Reject weak candidates.",
                  today="2026-07-01")
    print(demo)
