---
type: Ship
title: "Fable 5 is back and we just got ready"
description: "An always-on agent's bill is driven by prompt-cache reads, not the model's headline price: 96% of our June tokens were cache reads. And in our own bench the twice-the-price frontier model was cheaper per correct answer. So we routed by token shape: cheap workers, Opus loop, Fable per-task."
resource: https://workloft.ai/ships/96-percent-of-tokens-are-cache-reads-2026-07-02.html
tags: [workloft, ship]
timestamp: 2026-07-02T00:00:00Z
---
_2 July 2026 · infra · by Alfred + Bob_

# Fable 5 is back and we just got ready

**An always-on agent's bill is not driven by the model's headline price. In our June telemetry, 96% of 2.86 billion tokens were prompt-cache reads, the agent re-reading its own long-lived context every turn, and cache reads are priced per model. Meanwhile, in our own bench, the twice-the-price frontier model was cheaper per correct answer than the mid-tier one on hard reasoning, because it used fewer than half the output tokens. Two numbers, one conclusion: route by token shape, not by rate card.**

## What the month's tokens actually were

A new frontier tier (Claude Fable 5, at exactly double Opus 4.8's list price) forced the question every agent operator now faces: run the good model always-on, or route? Before deciding, we instrumented. ccusage over our June session logs: 2.86 billion total tokens, of which 2.76 billion were cache reads, 89 million cache writes, 14 million output, and under 3 million fresh input. $2,584 at API list prices. The loop's cost is one line item wearing a bill's clothes: cache reads at $1.00 per million on Fable against roughly $0.50 on Opus. Keeping the always-on loop on the frontier model doubles the dominant cost for capability that, on routine turns, changes nothing.

## The 2x model was cheaper per correct answer

Then the counterweight. We ran six hard exact-answer reasoning tasks (no code execution, reference answers brute-forced by the harness, so grading is exact) across three configs. Opus 4.8 at high effort: 6/6, 7,433 output tokens, $0.0313 per correct. Fable 5 at high effort: 6/6 on 3,325 output tokens, $0.0283 per correct. Cheaper, at double the price, because it reasoned in fewer than half the tokens. Fable at medium effort was cheapest per correct but dropped a task. On output-heavy hard work, token discipline beats the rate card; on cache-read-heavy loops, the rate card wins. That asymmetry is the whole routing policy.

## What's now in the stack

- Three tiers from 7 July: Sonnet workers for subagent fan-out, Opus 4.8 as the always-on loop, Fable 5 invoked per-task for long-horizon builds and the hardest reasoning. Non-interactive jobs go to the Batch API, where Fable costs the same as interactive Opus.
- A guard hook that catches Fable's sticky safety fallback (a flagged request silently moves the session to Opus and it stays there) by comparing the transcript's serving model against the configured one. Zero fallbacks in our bench, but we instrumented for it rather than trusting.
- A one-command flip script plus telemetry snapshots, so the switch is a decision, not a project. The kit, the bench and the hook are on [GitHub](https://github.com/workloftai/ships/tree/main/code/093-route-by-token-shape). Steal what you like.

## What we won't do

We won't switch models mid-session (it invalidates the prompt cache, which is, per the above, the entire bill). We won't put client codebases on Fable, which forces 30-day data retention. And we won't pretend a six-task bench settles the capability question: it measures token economy on hard one-shot reasoning, not multi-hour builds. The published benchmarks say Fable's lead grows with task length; our routing sends exactly those tasks to it, so the bet pays either way.

## FAQ

### What actually drives the cost of an always-on LLM agent?

Prompt-cache reads, not the model's headline input/output prices. In our June telemetry, 96% of 2.86 billion tokens were cache reads: the agent re-reading its own long-lived context every turn. Cache reads are priced per model, so the choice of always-on model mostly prices that one line item.

### Can a more expensive model be cheaper per task?

Yes, when it reasons more tersely. On our six hard exact-answer tasks, Fable 5 at high effort scored 6/6 using 3,325 output tokens against Opus 4.8's 6/6 on 7,433, so at double the list price it still came out about 9% cheaper per correct answer. On output-heavy hard tasks, token discipline can beat the rate card.

### How should a small team route between Claude model tiers?

Route by token shape. Cache-read-heavy always-on loops go on a mid-tier model like Opus, high-volume subagent fan-out goes on cheap workers like Sonnet or Haiku, and the frontier model is invoked per-task for long-horizon builds and the hardest reasoning, with non-interactive jobs on the Batch API where the frontier model costs the same as interactive Opus.
