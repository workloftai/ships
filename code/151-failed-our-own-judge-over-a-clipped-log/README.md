# We failed our own judge over a clipped log

If you run an LLM as a judge and log its reasoning, and anything downstream (a
meta-eval, a review, a dashboard rule) grades those logs, read this before it
bites you.

Our judge panel logs each vote's rationale. A nightly meta-eval grades those
logs. We clipped the rationale to 500 characters with a bare slice, which cut a
thorough four-axis rationale (selection / following / composition / reflection)
off mid-word. The meta-eval read the stub as "names four axes, stops after
three" and failed a perfectly good judge on the composition axis, for 38 days.
The model was never the problem. Our logger was.

## The fix, in two rules

1. **Never clip the copy your own logic still reasons over.** We were clipping
   the rationale on the vote object itself, so the panel's disagreement-map and
   minority-veto logic were also reasoning over a truncated string. Keep the
   working value whole; only cap the log copy.
2. **Clip word-safe, mark it, and budget it to fit.** A bare `s[:500]` cuts
   mid-word and reads as broken. Snap to the last word boundary, append a visible
   marker, and set the budget to the real content size (ours needed ~1500, not
   500). See [`wordsafe_clip.py`](wordsafe_clip.py), which is dependency-free.

```bash
python3 wordsafe_clip.py    # shows a bare slice vs the word-safe, marked clip
```

## Files

- `wordsafe_clip.py` — the portable, self-contained clip helper plus a demo.
- `test_rationale_composition.py` — the regression test we added (references our
  internal `vera.poll`, so it will not run outside our box, included as a
  reference for what to assert: returned value stays whole, logged copy keeps all
  axes, over-budget clips are word-safe and marked).

## The durable takeaway

The record you log is the record your evaluation grades. When your observability
truncates anything, ask one question: is something downstream grading the
truncation. If it is, you can fail your own system for work it did correctly, and
the failure will point at the wrong culprit.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
