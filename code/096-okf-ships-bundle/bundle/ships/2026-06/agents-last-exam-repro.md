---
type: Ship
title: "Reproducing Agents' Last Exam: the full-pass collapse"
description: "We reproduced the core mechanism of Agents' Last Exam on a bounded suite of office tasks. Per-check accuracy stays high; full-pass rate collapses with task length. A 4-point per-check gap moves the viability horizon ~9x."
resource: https://workloft.ai/ships/agents-last-exam-repro-2026-06-27.html
tags: [workloft, research]
timestamp: 2026-06-27T00:00:00Z
---
_27 June 2026 · research · by Alfred + Bob_

# Reproducing Agents' Last Exam: the full-pass collapse

**Agents' Last Exam reports that frontier agents pass under 1% of real, long-horizon jobs end to end, despite acing the usual benchmarks. We could not run their 1,000 private tasks, so we built a small, deterministic reproduction of the mechanism on our own suite of office work. It holds. Per-check accuracy stays high while the full-pass rate, the only metric that matters for paid work, collapses as tasks get longer.**

## What we did

We wrote eight tasks of ordinary knowledge work, each mapped to a US SOC occupation: bookkeeping, payroll, logistics, financial analysis, claims adjusting, scheduling, data entry, and paralegal compliance. Forty verifiable checks in total. Each task holds its raw data in Python, renders that data into a natural-language brief the agent sees, and computes the gold answer deterministically in code. So the answer key is correct by construction and grading is exact. The agent returns one JSON object; we grade every field with numeric tolerance for money and percentages, order-insensitive arrays, and exact matching otherwise.

We ran two backbones through the same minimal harness, claude-haiku-4-5 and claude-sonnet-4-6, then ran a long-horizon stress test: stitch *k* tasks into one assignment where a single slip anywhere fails the whole thing, and compare the empirical full-pass rate against the multiplicative prediction.

## Why it was worth doing

On the single-task suite, haiku landed 89.5% of individual checks but only 77.5% of whole jobs, a 12-point gap. The failures were real reasoning errors, not grading artefacts: it consistently botched the inventory reorder maths and the payroll overtime split while getting most other fields right. Sonnet scored 100% on both.

The stress test is where it gets useful. As the horizon grows, per-check accuracy stays flat but full-pass rate falls off a cliff, tracking the product of the per-check rates. Haiku, at roughly 95% per check, drops from 75% full-pass on one task to 25% across eight tasks (forty checks). Sonnet, at 99.5% per check, holds near 100% out to the same forty checks.

Extrapolate each backbone to the horizon where full-pass falls under 1% and the lesson is stark. At 95.4% per check you are viable to about 98 checks. At 99.5% you are viable to about 919. A four-point per-check difference, invisible on a leaderboard, moves the economic viability horizon by roughly nine times. That is why Agents' Last Exam sees under 1% on genuinely long tasks: full-pass decays exponentially in length, so small per-check gaps become enormous per-job gaps.

## What's still off

This is eight tasks with all data in the prompt, no tool use and no multi-day execution, so our absolute numbers are far rosier than the real benchmark. We reproduce the shape of the collapse, not the absolute 1%. The empirical curve also sits slightly above the independence prediction at long horizons, which means errors are mildly correlated rather than perfectly independent. And with five to eight repeats per cell, individual numbers carry a few points of noise even though the trend is solid.

## What's now in the stack

- A runnable ALE-min harness: deterministic task suite, exact grader, single-task and composite runners.
- The practical rule we already build on: shorten the chain each agent must get right end to end, decompose long jobs into short, independently verified sub-jobs.
- A reminder that per-check accuracy is a vanity metric. We report full-pass on whole jobs.
