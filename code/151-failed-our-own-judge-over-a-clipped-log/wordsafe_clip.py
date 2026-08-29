#!/usr/bin/env python3
"""
wordsafe_clip — length-cap a string for logging WITHOUT creating a stub that a
downstream evaluator will misread as an incomplete output.

The bug this came from: our LLM-judge panel logs each vote's rationale, and a
nightly meta-eval grades those logs. We clipped the rationale to 500 chars with a
bare slice, which cut a thorough four-axis rationale off mid-word ('...call
succe'). The meta-eval read the stub as "claims four axes but trails off" and
failed a perfectly good judge for weeks. The record you log is the record you
grade.

Two rules fell out of it:
  1. Clip on a word boundary and append a VISIBLE marker, so a trimmed field
     reads as deliberately trimmed, not broken.
  2. Budget the clip to fit the real content (ours needed ~1500, not 500), and
     never clip the copy your own logic still reasons over, only the log copy.

Dependency-free. Steal it.
"""


def wordsafe_clip(s: str, limit: int, marker: str = " […]") -> str:
    """Cap `s` at `limit` chars, backing off to the last whitespace boundary
    inside the budget (if one is reasonably close) and appending `marker`. A
    string already within budget is returned untouched."""
    s = s or ""
    if len(s) <= limit:
        return s
    budget = max(0, limit - len(marker))
    head = s[:budget]
    cut = head.rfind(" ")
    if cut > budget * 0.6:          # only snap to a word boundary if one is near
        head = head[:cut]
    return head.rstrip(" \t\n,;:.…-") + marker


if __name__ == "__main__":
    bad = "a" * 40 + " Efficiency: the response is concise and correct enough"
    # bare slice cuts mid-word:
    print("bare slice :", repr(bad[:50]))
    # word-safe clip does not, and marks the trim:
    print("word-safe  :", repr(wordsafe_clip(bad, 50)))
    # in-budget strings are untouched:
    print("untouched  :", wordsafe_clip("short and complete.", 100))
