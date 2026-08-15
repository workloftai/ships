# skiller-spike — a skill, not a bigger model

Can a natural-language *skill*, written by a strong model from a small model's
own mistakes, lift a free local model to match a paid cloud model? We ran the
core loop from SKILLER ([arXiv:2608.10538](https://arxiv.org/abs/2608.10538))
with our own pieces to find out.

## Result

On a held-out extraction task (messy invoice records with distractors → normalised
JSON):

| | score on held-out test |
|---|---|
| cloud model (gemini-2.5-flash) | 1.000 |
| free local model (Qwen-2.5-7B), no skill | 0.938 |
| free local model **+ evolved skill** | **1.000** |

One skill-refinement iteration closed **100% of the gap**. Kill gate was 60%.
The evolved skill contains only general rules (see `result.json`) — no memorised
answers — and the strong model that wrote it never saw the test set.

## The thing the paper's framing hides

SKILLER is described as a "reinforcement learning framework", which sounds like
GPU training. It isn't. No weights change. It's an orchestration loop:

```
strong ACTOR writes a skill  ->  small EXECUTOR runs the task with it
     ^                                      |
     |   refine skill from the mistakes  <--+  deterministic REWARD (field match)
```

Only a natural-language skill block evolves, driven by the executor's own errors.
That's why it's cheap to reproduce: an afternoon, not a cluster.

## Run it

```bash
GOOGLE_API_KEY=... OLLAMA_MODEL=qwen2.5:7b-instruct python3 skiller_spike.py
```

- **actor** = gemini-2.5-pro (strong, writes/refines the skill)
- **executor** = your local Ollama model (free)
- **ceiling** = gemini-2.5-flash (the cheap cloud model you'd replace)

Train (8 records) drives skill refinement; test (8) is held out and only scored.

## Honest limits

- The gap was small (6 points) — the 7B was already decent, and the skill fixed
  one patterned confusion (buyer vs seller, total vs VAT, ref vs invoice-number).
  This shows the loop **works cheaply**, not that it closes a *large* gap. The
  next test is a task where the local model starts far behind.
- One iteration was enough here, so the multi-round refinement dynamics didn't
  get exercised.
- The reward is deterministic field-match because the task has checkable answers.
  For open-ended tasks you'd swap in a model-graded reward (an LLM judge), which
  adds cost and noise.
- Small test set, single task, single run. A spike, not a benchmark.

The strategic point stands: where a skill can close the gap, that task moves to
the free local tier for good — zero marginal cost, runs offline, no data leaves
the box.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
