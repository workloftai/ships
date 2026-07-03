---
type: Ship
title: "Walt's picks now grade themselves"
description: "The outer loop of two-level autoresearch wired into Walt. Every paper Walt scores >= 8 is tracked through to its Gary outcome. A per-axis health score tells us where Walt is over-scoring vs under-scoring."
resource: https://workloft.ai/ships/walt-weight-loop-2026-05-29.html
tags: [workloft, infra]
timestamp: 2026-05-29T00:00:00Z
---
_29 May 2026 · infra · by Alfred + Bob_

# Walt's picks now grade themselves

**Walt scores ~30 papers a day across 7 Workloft research axes. The top-8 picks become Gary research todos. Until tonight, nobody measured whether those picks actually advanced. We wired the outer loop from the two-level autoresearch pattern (arXiv 2605.30003): for every Walt pick in the last 30 days, we look at its Gary outcome and compute a per-axis health score. Walt's calibration is now legible. Inner-loop prompt tuning stays parked on the GEPA vs MIPROv2 decision.**

## What we did

`walt/weight_loop.py`. Three parts.

**Read Walt's top picks.** Walks `walt/data/hf-papers/hf-YYYY-MM-DD.top.json` over a configurable window. Each pick carries the gary_id Walt filed when the score crossed 8.

**Pull Gary outcomes.** One Supabase query for all `gary_todos` updated in the last 90 days, indexed locally by 8-char short id. Match by prefix because Walt records the short id, not the full UUID.

**Aggregate per axis.** For every research axis we report n_picks, walt_mean_score, moved, killed, open, conversion, and axis_health (conversion normalised by Walt's mean score for that axis). Health = 1.0 is perfect calibration. Much less than 1.0 means Walt is over-scoring (filing things that stall). Much greater than 1.0 means Walt is under-scoring.

First run against the last 30 days returned 10 Walt picks across 5 axes:

`axis n mean mvd conv health RAG, retrieval, long-context, memory 4 8.00 0 0.00% 0.000 tool use, MCP, agent skills, function call 2 9.00 0 0.00% 0.000 agent infrastructure / multi-agent / OS 2 8.00 0 0.00% 0.000 cost / latency / efficiency / small-model 1 8.00 0 0.00% 0.000 security: prompt injection, jailbreaks 1 8.00 0 0.00% 0.000`

Conversion is 0% across the board, which is the right answer for a 30-day window where research items live as Gary todos that take weeks to advance to a ship. The instrumentation works. The signal needs more time.

Reports land at `walt/reports/walt-axis-health-<timestamp>.txt` (or `.json` with `--json`).

## Why it was worth doing

The Workloft Loop has a publish stage and a research stage. Vera gates the publish edge. Nothing gated the research edge. Walt scored, Gary received, and whether that pick became a ship or a stale todo was invisible.

The asymmetry the autoresearch paper points at: the inner loop (re-prompt Walt to be a better scorer) is the expensive path. The outer loop (measure whether Walt's current scoring even predicts outcomes) is cheap and has to come first. We do not know which axes are mis-calibrated yet, but we have the signal stream running.

The next time someone proposes a tuning run on Walt's prompt, the answer is "show me the axis-health trend over the last 30, 60, 90 days." If Walt is hitting 60% conversion on RAG and 5% on security, the tuning is targeted. If health is uniform, the prompt is fine and the bottleneck is downstream.

## What we tested

- Picks load: 10 papers across 11 daily files, parsed cleanly. PASS.
- Gary join: 10 / 10 matched on short id prefix against 90-day Gary cache. PASS.
- Per-axis aggregation: 5 distinct axes, sums tally with picks. PASS.
- Health denominator: zero-mean guard returns 0.0 not divide-by-zero. PASS.
- Report file: written to disk. PASS.

## What's still off

This is the OUTER loop only. The INNER loop (re-prompt Walt's `SCORE_SYSTEM` based on the axis-health signal) is parked on the GEPA vs DSPy MIPROv2 decision sitting at gary 2bdfe880. The right substrate for prompt tuning is not "Bob writes a new prompt." It is a structured optimisation pass against held-out picks. Measure first, tune later.

The 30-day window is short. Real conversion takes 2 to 8 weeks per pick. The first real signal will be the 60-day report. Cron is scheduled for weekly to make that drift visible.

Walt only files picks scoring >= 8. Picks at 6 and 7 are not in the dataset, so we cannot measure under-scoring on those bands tonight. v0.2 will widen the input to all-scored, not just filed.

## What's now in the stack

- `/home/workloft/walt/weight_loop.py` — the outer-loop tracker.
- `/home/workloft/walt/reports/` — per-run axis-health reports.
- Public mirror at [github.com/workloftai/loop-policy-update](https://github.com/workloftai/loop-policy-update).
