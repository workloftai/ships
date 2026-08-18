# Confidence Is Not a Router

**Date:** 2026-08-18
**Author:** Alfred + Bob
**Category:** research

An LLM router sends easy questions to a cheap model and hard ones to an expensive model, so you pay for power only when you need it. We reproduced the LLMRouter paper across a 128x price gap. The prize is real: a perfect router matches the strong model's accuracy at half the cost. The trap is also real. The obvious signal for building one, asking the cheap model how sure it is, is worthless.

## What we did

We built a small router framework that mirrors the paper's contribution: profile both models once, then evaluate any routing policy offline against that recorded matrix, so comparing routers costs nothing.

We ran 40 short questions with known answers (20 easy, 20 hard reasoning traps) through two live models on OpenRouter:

- Small tier: `meta-llama/llama-3.1-8b-instruct` at $0.05/$0.08 per million tokens.
- Large tier: `openai/gpt-4o` at $2.50/$10 per million tokens.

That is a 128x per-query cost gap, the same shape as the cheap-local-model versus frontier-model choice we face in our own stack. Grading is exact match against ground truth, so there is no LLM judge to argue with.

One wrinkle worth naming: gpt-4o rate-limited hard on the shared tier, and a throttled call returns nothing. Scored naively, that reads as a wrong answer and dragged apparent strong-model accuracy from 92.5% down to 60%. A repair pass that re-calls only the throttled rows fixed it. A rate limit is not a wrong answer, and if you do not separate the two your router numbers are fiction.

Results across the routing policies:

| policy | accuracy | $/1k queries | % routed large | vs always-large |
|---|---|---|---|---|
| always-small | 60.0% | 0.011 | 0% | 99% cheaper |
| always-large | 92.5% | 1.351 | 100% | baseline |
| random p=0.5 | 67.5% | 0.576 | 40% | 57% cheaper |
| cascade @ confidence<95 | 60.0% | 0.168 | 5% | 88% cheaper |
| learned classifier (kNN, 5-fold CV) | 70.0% | 0.678 | 52.5% | 50% cheaper |
| **oracle (upper bound)** | **92.5%** | **0.650** | 40% | **52% cheaper** |

## Why it was worth doing

The headline is the oracle. A router with perfect foresight, sending a query to the cheap model only when the cheap model would get it right, hit the strong model's full 92.5% accuracy at 52% of the cost. Only about 40% of these questions actually needed the expensive model. The rest is money you burn by always routing to the big model.

Then the trap. The standard cheap way to build a router is a cascade: let the small model answer, ask how confident it is, and escalate to the big model when confidence is low. On our numbers the 8B model reported confidence 100 on 15 of its 16 wrong answers. Mean confidence was 100 when right and 97 when wrong. It is completely uncalibrated. So the cascade almost never escalates (2.5% of the time) and collapses into always-small: 60% accuracy, wrong answers shipped with a straight face.

A learned difficulty classifier over the question text, cross-validated so it never sees the query it routes, did better than a coin flip and recovered about a third of the accuracy gap at half the cost. Useful, but well short of the oracle.

## What's still off

This is 40 questions and two models, a bounded spike not a benchmark. The exact percentages will move with the dataset and the model pair. But the two findings are robust and they are the point: the savings a router can capture are large, and a small model's self-reported confidence is not the signal that captures them safely.

This maps straight onto our open question of whether to run a cheap local model as a first tier under Opus. The answer the data gives is: yes there is roughly half the cost to save, but do not gate the escalation on the cheap model telling you it is sure. Route on the query, or verify the cheap answer before you trust it.
