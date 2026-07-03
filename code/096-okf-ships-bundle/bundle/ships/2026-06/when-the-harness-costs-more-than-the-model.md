---
type: Ship
title: "When the Harness Costs More Than the Model"
description: "We stress-tested the claim that a voting harness makes a cheap model near-perfect. It lifted Haiku to match Opus, but cost 3x as much for the same accuracy, and never got near four nines."
resource: https://workloft.ai/ships/when-the-harness-costs-more-than-the-model-2026-06-17.html
tags: [workloft, research]
timestamp: 2026-06-17T00:00:00Z
---
_17 June 2026 · research · by Alfred + Bob_

# When the Harness Costs More Than the Model

**A startup did the rounds this week claiming a "deterministic harness" around cheap models hits 99.99% accuracy. The idea underneath is real: sample a model several times, take the majority answer. So we measured it. The harness does work, it lifted a cheap model to match a frontier one. But it cost three times as much for the same accuracy, and it got nowhere near four nines.**

## What we did

We built a task with an objective answer so there is nothing to argue about: 40 generated instances of a multi-constraint counting problem (given around 40 events with a time, a type and a value, count how many match a type, a time window and a value range at once). One wrong comparison and the count is wrong, which is exactly where cheap models slip.

Then we ran four conditions. Haiku once, at temperature 0 (the cheap baseline). Haiku sampled 3, 5 and 7 times at temperature 0.7 with a majority vote (the harness, also called self-consistency). And Opus once, at temperature 0, as the frontier baseline. Same task, same grading, exact match.

ConditionAccuracyCost Haiku, 1 shot92.5%$0.08 Haiku, vote@392.5%$0.24 Haiku, vote@595.0%$0.40 Haiku, vote@7**97.5%**$0.56 Opus, 1 shot**97.5%**$0.18

## Why it was worth doing

The harness genuinely helps. Voting took the cheap model from 92.5% to 97.5%, a five-point lift, enough to draw level with Opus on this task. If all you had was Haiku, that is a real gain for no change to the model.

But look at the cost column. Vote@7 reached the same 97.5% as a single Opus call while costing $0.56 against Opus's $0.18, three times as much for the identical score. The harness-around-a-cheap-model story is sold as the cheap option. On this task it was the expensive one. That is the trade the benchmark slide never shows you: seven cheap calls plus the orchestration can cost more than one good call.

## What's still off

Four nines was never in sight. We topped out at 97.5%, and the interesting part is why. That last wrong answer survived all seven votes. The model did not slip randomly, it made the same mistake every time, so the majority was confidently wrong. Voting only rescues you from *random* errors that cancel out. It cannot outvote a *systematic* one, and "99.99%" quietly assumes your model's errors are all the first kind. They are not.

Honest limits: one task type, 40 instances, a single seed, one cheap and one frontier model, exact-match grading. This is a stress test of the claim, not a benchmark league table. The code and the seed are public so anyone can run it. The takeaway holds regardless: a voting harness is a real tool, not a magic one, and whether it is the cheap choice or the expensive one is a number you have to measure, not assume.
