# Our eval killed finished answers as truncated

If you run an LLM eval and it *holds* or *rejects* outputs it thinks are
incomplete, make sure it can tell a finished answer from a cut-off one. Ours
couldn't, and it was the single biggest source of its false failures.

Our nightly eval refused to grade any output that came wrapped in the model
router's `{model, provider, text_preview}` envelope, on the theory that a preview
must be a truncation. But routed calls put their *whole* short output inside that
envelope. So complete, correct classifications (score, axis, hook, all present)
were held as truncated, escalated to a strong reviewer, and killed for "missing
fields" that were sitting inside the preview string. An evaluator that cannot tell
whole from broken does not just miss problems, it invents them against the work
that was fine.

## The fix, in one predicate

[`preview_complete.py`](preview_complete.py) is the whole idea, dependency-free.
A preview is complete if it parses as JSON (the structured output finished), or
it is comfortably under the logging cap and ends on a clean boundary rather than
mid-word. Use it before you hold an output as truncated:

```python
from preview_complete import preview_complete

if "text_preview" in response:
    tp = response["text_preview"]
    if preview_complete(tp):
        candidate = tp          # the whole output, judge it on merit
    else:
        hold_for_review()       # genuinely cut off
```

```bash
python3 preview_complete.py    # finished / fenced -> True, cut-off -> False
```

## Verified

On the exact output that was being killed for a missing score, axis and hook: it
now passes at full confidence, and a genuinely truncated preview is still held.
`test_preview_gate.py` pins both (it references our internal eval, so it will not
run outside our box; it is here as the spec for what to assert).

## The lesson

A false failure that blames good work is the most expensive kind, because it
sends you to fix something that was never wrong. If your grader ever decides an
output is "incomplete", give it a way to be sure, or it will punish the work that
finished cleanly and happened to be wrapped.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
