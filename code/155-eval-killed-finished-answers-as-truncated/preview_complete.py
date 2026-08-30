#!/usr/bin/env python3
"""
preview_complete — tell a finished output from a genuinely truncated one.

The bug this came from: our eval refused to grade any logged output that came
wrapped in the router's {model, provider, text_preview} envelope, on the theory
that a preview must be a truncation. But routed calls put their WHOLE short output
inside that envelope, so complete, correct classifications were held as truncated,
escalated, and then killed for fields that were present inside the preview string.
It was the single biggest source of our eval's false failures.

The fix is this one predicate. A preview is complete if it parses as JSON (the
structured output finished), or it is comfortably under the logging cap and ends
on a clean boundary rather than mid-word. Use it before you hold an output as
"truncated": a complete one should be unwrapped and judged on merit; only a
genuine cut-off should be held.

Dependency-free.
"""

import json
import re

# The length your logger caps a preview at. A preview at (or near) the cap may
# have lost content past it; one well under it did not.
PREVIEW_CAP = 500


def preview_complete(tp: str, cap: int = PREVIEW_CAP) -> bool:
    tp = (tp or "").strip()
    if not tp:
        return False
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", tp).strip()
    try:
        json.loads(body)          # valid JSON means the output finished
        return True
    except Exception:
        pass
    # Non-JSON: complete only if clearly under the cap and ending cleanly.
    return len(tp) < cap - 20 and tp[-1:] in ".!?)\"'}]"


if __name__ == "__main__":
    finished = '{"score": 4, "axis": "infra", "hook": "a real hook", "effort": 3}'
    fenced = '```json\n{"score": 2, "axis": "x"}\n```'
    cutoff = '{"score": 4, "axis": "other", "hook": "This blog post discusses the imp'
    for label, s in [("finished", finished), ("fenced", fenced), ("cut-off", cutoff)]:
        print(f"{label:9s} -> complete={preview_complete(s)}")
