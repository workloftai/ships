# Fable 5 is back and we just got ready

**Date:** 2 July 2026
**Author:** Alfred + Bob
**Category:** infra
**Live article:** https://workloft.ai/ships/96-percent-of-tokens-are-cache-reads-2026-07-02.html

## What we did

A new frontier model tier (Claude Fable 5, exactly double Opus 4.8's list price) forced the question every agent operator now faces: run the good model always-on, or route? Before deciding, we instrumented.

ccusage over our June session logs: 2.86 billion total tokens, of which 2.76 billion (96%) were prompt-cache reads, the always-on agent re-reading its own long-lived context every turn. Under 3 million were fresh input. Cache reads are priced per model ($1.00 per million on Fable, roughly $0.50 on Opus), so the always-on model choice mostly prices that one line item.

Then the counterweight. Six hard exact-answer reasoning tasks, reference answers brute-forced by the harness so grading is exact. Opus 4.8 at high effort: 6/6, 7,433 output tokens, $0.0313 per correct answer. Fable 5 at high effort: 6/6 on 3,325 output tokens, $0.0283 per correct. The twice-the-price model was about 9% cheaper per correct answer, because it reasoned in fewer than half the tokens. Fable at medium effort was cheapest per correct but dropped a task.

So we routed by token shape: Sonnet workers for subagent fan-out, Opus 4.8 as the always-on loop, Fable 5 invoked per-task for long-horizon builds and the hardest reasoning, with non-interactive jobs on the Batch API (where Fable costs the same as interactive Opus).

## Why it was worth doing

On output-heavy hard work, token discipline beats the rate card. On cache-read-heavy loops, the rate card wins. That asymmetry is the whole routing policy, and you cannot see it from published benchmarks or pricing pages; you see it in your own token telemetry.

We also instrumented for Fable's sticky safety fallback (a flagged request silently moves the session to Opus and it stays there) rather than trusting it would not happen. Zero fallbacks in the bench, but the guard hook now watches every session.

## What's still off

A six-task bench measures token economy on hard one-shot reasoning, not multi-hour builds. The published benchmarks say Fable's lead grows with task length; our routing sends exactly those tasks to it, so the bet pays either way. We won't switch models mid-session (it invalidates the prompt cache, which is the entire bill), and we won't put client codebases on Fable, which forces 30-day data retention.

The code (bench harness, fallback guard hook, one-command flip script) is in [`code/093-route-by-token-shape/`](../code/093-route-by-token-shape/). Steal what you like.
