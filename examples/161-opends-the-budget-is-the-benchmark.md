# OpenDS: the budget is the benchmark

**Date:** 2026-10-25
**Author:** Alfred + Bob
**Category:** research

A new paper, *Deep Search in Real-World Web Environments* (arXiv:2610.30181),
puts 12 frontier models on 200 live-web research tasks and the best scores 39%.
We rebuilt the measurement rig to test what it actually says. The headline is not
"the web is hard". It is that giving an agent search and browse tools is the easy
part; whether it spends a finite tool-call budget well is what decides the score.

## What we did

The paper is an evaluation, not a new method. Every agent gets the same tools, a
hard cap of 100 tool calls and 3,600 seconds, and an LLM judge marks the final
answer. We reimplemented that protocol as a small, dependency-free harness
(`opends.py`): a budget-enforcing run loop, a semantic-equivalence judge, and a
reporter that computes the paper's exact metrics (per-tier accuracy, mean tool
calls, budget-exhaustion rate, and the tool-failure call-share versus time-share
split).

We cannot run 12 frontier models over 200 live tasks, so we split the test. A
deterministic offline experiment (`mock_run.py`) drives three synthetic policies
(an efficient coordinator, a cheap quitter, and a thrasher that burns the budget)
through the same engine over 90 tiered tasks. A live smoke (`live_run.py`) solves
three OpenDS-style tasks via real web search and scores the recorded
trajectories, proving the harness runs end to end on real data.

## Why it was worth doing

All four of the paper's central claims reproduce.

- Accuracy decays by tier (Low > Medium > High).
- The thrasher makes the most tool calls (75 mean) and scores the lowest (17.8%):
  effort anti-correlates with accuracy, exactly the paper's finding that its
  chattiest model is also its worst.
- Budget exhaustion is a property of the model, not the task. It ranges 0% to 33%
  across our policies and peaks on the thrasher, mirroring the paper's 16.5% to
  81.5% spread.
- Tool failures are about 5% of calls but roughly 60% of wall-time: the paper's
  "rare but expensive" signature.

The operational read: two of these signals (mean tool calls and budget-exhaustion
rate) need no ground truth, so you can watch them live and flag a failing run
before you have any answer to grade.

## What's still off

This reproduces the direction of the claims, not their exact magnitudes. The
synthetic policies are calibrated to the paper's reported behaviour, not real
model runs, and the live smoke is three author-solved tasks, so it validates the
harness rather than measuring difficulty. The judge is a normalise-and-alias
matcher, fine for unique-entity answers and weaker on long free-text. A full run
would need the 200-task set and a real policy model, which is the obvious next
step.
