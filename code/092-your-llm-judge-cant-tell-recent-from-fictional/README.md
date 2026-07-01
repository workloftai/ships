# Your LLM judge can't tell recent from fictional

An LLM used as a judge, grader or reviewer has no reliable sense of what day it
is. Show it a candidate that mentions an event, release or version newer than
its training data and it cannot tell "recent and real" from "fictional". A
kill-biased judge resolves that doubt the cheap way: it rejects the thing and
calls the date hypothetical.

We hit this on a live evaluation. A three-model judge panel killed a fresh
research finding unanimously at 0.98 confidence, and every kill shot was about
the calendar, not the argument. The panel was grading its own training cut-off.

## The fix

Prepend a short grounding preamble to the judge's system prompt that:

1. States **today's real date**, injected at call time.
2. Forbids **"it postdates what I know"** as a reason to reject.

That is the whole change. No date-stripping regex, no scrubbing of the
candidate, nothing that breaks on an oddly phrased date. It is inert on a prompt
that never mentions a date, and it works whether your judge is strict or
lenient.

## Files

- `temporal_grounding.py` - the pattern. `ground(system_prompt, today=None)`
  returns your judge's system prompt with the grounding preamble on top.
  Dependency-free, standard library only.
- `test_temporal_grounding.py` - run with `python3 test_temporal_grounding.py`.

## Use it

```python
from temporal_grounding import ground

system_prompt = ground(YOUR_JUDGE_SYSTEM_PROMPT)   # uses today's date
# then send system_prompt as the judge's system message as usual
```

Pin the date for tests or from a caller that already knows the clock:

```python
system_prompt = ground(YOUR_JUDGE_SYSTEM_PROMPT, today="2026-07-01")
# or set the JUDGE_TODAY environment variable
```

## What it does not do

Grounding stops the judge rejecting something for being recent. It does not let
the judge verify a claim it has never seen. A genuinely false "recent" fact
still needs a real source or a tool check. This removes a false negative, it
does not add knowledge.
