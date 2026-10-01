# 178 · Forecasting the agent bill didn't save us money

Write-up: https://workloft.ai/ships/forecasting-the-agent-bill-2026-10-01.html

TokenCast ([arXiv 2609.35760](https://arxiv.org/abs/2609.35760)) forecasts how many
tokens an agent task will burn while it is still running, and reports 21.3% fewer
tokens than a fixed budget in an offline replay on SWE-bench-style traces. We wanted to
know whether that would beat the fixed caps in our own budget guard
([113-budget-floor](../113-budget-floor)), so we replayed a month of our own agent
tasks through it.

The authors have not released their code yet, so `tokencast_lite.py` is our own
re-implementation from the abstract, not theirs. Each model call is a segment with two
numbers: what it cost, and how much it grew the context that every later call re-reads.
Composing them gives a bill that grows quadratically with the remaining calls. The
forecast refreshes after every call with plain arithmetic, no extra model calls. The
only fitted part is how many more calls a task tends to make, given how many it has
made so far.

## Result on our fleet

707 real tasks, 6,593 model calls, 29 Aug to 1 Oct 2026, from Claude Code session logs.
Fit on the oldest 70%, tested on the newest 213 tasks.

Median error against the final bill, k calls into a task:

| after k calls | fixed guess | naive (cost so far x expected length) | tokencast_lite |
|---|---|---|---|
| 1 | 61% | 56% | 56% |
| 3 | 62% | 38% | 35% |
| 5 | 68% | 38% | 36% |
| 10 | 77% | 37% | 42% |

Budget replay (stop a task early once the forecast says it will blow the cap anyway,
compared with a fixed cap at the same or better completion rate): 9.5% fewer tokens at
the tightest useful cap, under 1% at every cap that lets roughly 70% or more of tasks finish.
Weighted by price (cache reads at a tenth, output at five times input) it is 2% at best.

Why: 87% of our tokens are calls re-reading what was already in the window when the
task started (median 152k tokens: system prompt, tools, memory, earlier conversation).
Each call adds about 1k. There is almost no context growth for the method to model, so
the bill is call count times starting context, and any forecaster is only guessing the
call count.

`demo.py` shows the same thing on synthetic data. With a heavy start and small growth,
tokencast_lite and the naive baseline tie. With a small start and big growth (a coding
agent reading files), tokencast_lite cuts the error after five calls from 52% to 39%.

## Files

- `extract.py`: Claude Code session logs to per-task token traces. Numbers only, no content.
- `tokencast_lite.py`: the forecaster, plus the fixed and naive baselines.
- `replay.py`: forecast error at checkpoints, and the budget-control replay.
- `demo.py`: runs with no data and no keys.
- `test_tokencast_lite.py`: tests.

```bash
python3 demo.py
python3 extract.py ~/.claude/projects traces.json
python3 replay.py traces.json results.json
```

Our own traces stay private. The tables above come from `replay.py` run on them.

## What's still off

This is a re-implementation from a 200-word abstract. Their learned segment
representation is probably richer than ours, and their traces grow far more than ours
do. The "budget replay" assumes stopping a task early is free, which it is not: someone
has to pick it up again. And a task here is one Claude Code turn, which is a rougher
unit than one SWE-bench issue.
