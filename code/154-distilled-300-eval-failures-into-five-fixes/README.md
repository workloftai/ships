# distill — turn a pile of eval failures into a short list of root-cause fixes

If you run an LLM eval over your agents, you accumulate failures: a verdict and a
reason, night after night, the same problems re-reported as separate tickets.
This reads them, clusters them by who failed and how, and asks a model to distil
each cluster into ONE root cause, whose fault it is (agent, rubric, or logging),
and one concrete fix.

The point is not automation for its own sake. It is to collapse N scattered
failures into a handful of things worth fixing, and to surface the uncomfortable
share of "failures" that are the eval's own fault, not the agent's.

```bash
python3 distill.py --min-cluster 4 --out distilled.json
```

## What we found on our own eval

303 failures across 2,672 graded outputs, distilled to five clusters. The fault
split (see [`distilled.example.json`](distilled.example.json)):

- **221 logging** — the eval was grading a truncated *preview* of the output, so
  real fields looked missing and complete rationales looked cut off. Same bug
  across four agent actions.
- **60 agent** — genuine, small faults (a null field, a wrong category, a list
  passed as a Python string instead of JSON).
- **9 rubric** — stale criteria failing correct work.

Three quarters of our eval's failures were one bug class in our own logging, not
agent quality. We would not have seen the ceiling was that high without
collapsing the pile first.

## Make it yours

`distill.py` reads our eval's score log (`vera/scores/vera_scores.jsonl`) and
routes model calls through our internal router, so this exact file will not run
outside our box. The reusable shape is small and portable: `load_kills()`
(group your failures by a key), and `distill_cluster()` (the system prompt that
asks for `{root_cause, fault, fix}` as strict JSON, with a model fallback).
Point them at your own failure store.

## Honest limits

The distillation is a model reading reasons, so a root cause is a strong
hypothesis, not a proven diagnosis. It clusters by one key, so cross-cutting
patterns only show up when you read the fault column. And it distils, it does not
fix. Reading a failure is cheap; the cure is still the work.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
