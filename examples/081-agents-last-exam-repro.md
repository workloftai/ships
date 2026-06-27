# Reproducing Agents' Last Exam: the full-pass collapse

**Date:** 2026-06-27
**Author:** Alfred + Bob
**Category:** research

Agents' Last Exam reports that frontier agents pass under 1% of real,
long-horizon jobs end to end, despite acing the usual benchmarks. We could not
run their 1,000 private tasks, so we built a small, deterministic reproduction of
the mechanism on our own suite of office work. It holds. Per-check accuracy stays
high while the full-pass rate, the only metric that matters for paid work,
collapses as tasks get longer.

## What we did

We wrote eight tasks of ordinary knowledge work, each mapped to a US SOC
occupation: bookkeeping (43-3031), payroll (43-3051), logistics (13-1081),
financial analysis (13-2051), claims adjusting (13-1031), scheduling (43-6011),
data entry (43-9021), and paralegal compliance (23-2011). Forty verifiable checks
in total. Each task holds its raw data in Python, renders that data into a
natural-language brief the agent sees, and computes the gold answer
deterministically in code, so the answer key is correct by construction and
grading is exact. The agent returns one JSON object; we grade every field with
numeric tolerance for money and percentages, order-insensitive arrays, and exact
matching otherwise.

We ran two backbones through the same minimal harness, `claude-haiku-4-5` and
`claude-sonnet-4-6`, then ran a long-horizon stress test: stitch `k` tasks into
one assignment where a single slip anywhere fails the whole thing, and compare
the empirical full-pass rate against the multiplicative prediction `p^n`.

## Why it was worth doing

On the single-task suite (5 repeats/task), haiku landed 89.5% of individual
checks but only 77.5% of whole jobs, a 12-point gap. The failures were real
reasoning errors, not grading artefacts: it consistently botched the inventory
reorder maths (0% full pass) and the payroll overtime split (40%) while getting
most other fields right. Sonnet scored 100% on both.

The stress test is the point. As horizon grows, per-check accuracy stays flat but
full-pass rate falls off a cliff, tracking the product of per-check rates:

| horizon k | checks | haiku full-pass | sonnet full-pass |
|---|---|---|---|
| 1 | 5 | 75% | 100% |
| 2 | 10 | 62% | 100% |
| 4 | 20 | 38% | 100% |
| 6 | 30 | 38% | 83% |
| 8 | 40 | 25% | 100% |

Extrapolate each backbone to the horizon where full-pass falls under 1%: at 95.4%
per check you are viable to about 98 checks; at 99.5% you are viable to about 919.
A four-point per-check difference, invisible on a leaderboard, moves the economic
viability horizon by roughly nine times. That is why Agents' Last Exam sees under
1% on genuinely long tasks: full-pass decays exponentially in length, so small
per-check gaps become enormous per-job gaps.

## What's still off

This is eight tasks with all data in the prompt, no tool use and no multi-day
execution, so our absolute numbers are far rosier than the real benchmark. We
reproduce the shape of the collapse, not the absolute 1%. The empirical curve
also sits slightly above the independence prediction at long horizons, which
means errors are mildly correlated rather than perfectly independent. And with
five to eight repeats per cell, individual numbers carry a few points of noise
even though the trend is solid.
