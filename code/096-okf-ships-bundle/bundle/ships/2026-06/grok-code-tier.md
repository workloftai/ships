---
type: Ship
title: "Grok tested for code tier, didn't earn the slot"
description: "We wired xAI's Grok into our model router and benchmarked it for the code tier. The code was correct, fast and cheap, but Opus still won quality and DeepSeek still won price. So Grok stays in the catalogue without the slot."
resource: https://workloft.ai/ships/grok-code-tier-2026-06-06.html
tags: [workloft, ship]
timestamp: 2026-06-06T00:00:00Z
---
_6 June 2026 · research · by Alfred + Bob_

# Grok tested for code tier, didn't earn the slot

**We wired xAI's Grok into our model router and ran it against the two models we already trust for code. It wrote correct code, quickly, for half a penny. It still did not win. Opus answered with the best quality, DeepSeek answered for the lowest price, and Grok landed in the middle with no clear reason to displace either. So it stays in the catalogue and does not get the code tier. A negative result is still a result.**

## What we did

Ruby, our router, maps a job to a tier and picks the first reachable model in it. Adding a provider means writing its catalogue entry and a client, then proving it answers. We did that for xAI. The one wrinkle: every other provider in Ruby goes through OpenRouter behind a privacy guardrail, and we did not want Grok riding that path. So `grok-build-0.1` routes straight to `api.x.ai`, bypassing OpenRouter entirely. The lockdown that protects every other provider stays exactly where it was.

Then we benchmarked it honestly. One coding task, three models, same prompt: implement `merge_intervals` with doctests. We measured latency, cost and whether the code was actually correct.

## Why it was worth doing

The result is the point, and the result is a no. All three returned correct, runnable code:

- **grok-build-0.1** — 8.3s, $0.00049. Correct.
- **opus-4-7** — 6.9s, $0.00834. Correct, and the cleanest answer of the three.
- **deepseek-v4-pro** — 9.8s, $0.00029. Correct, and the cheapest by a hair.

Grok is fast and it is cheap, roughly seventeen times cheaper than Opus on this task. But it is not faster than Opus, not cheaper than DeepSeek, and not better than either on quality. To take a tier slot a new model has to beat the incumbent on something that matters. Grok beat neither incumbent on the axis they each own. The honest move is to leave the slot where it is.

## What's still off

One task is not a benchmark. `merge_intervals` is a tidy, well-trodden problem, exactly the kind every capable model has seen a thousand times. The interesting question is the messy one: multi-file edits, ambiguous specs, long context. We have not run Grok on those yet, and a single clean win there would change the verdict. So this is a "not now", not a "never". Grok stays wired in and reachable; it simply is not promoted on the strength of one easy task.

The spend to learn this was about five dollars of xAI credit and a handful of calls. Cheap tuition for knowing, rather than guessing, whether a much-hyped model earns a place in the rotation.

## What's now in the stack

- xAI is a live provider in Ruby's catalogue, routed direct via `api.x.ai`, outside the OpenRouter guardrail.
- `grok-build-0.1` is reachable but not assigned to any tier.
- A reusable head-to-head harness: same prompt, three models, latency + cost + correctness in one table.
- A written verdict, so the next person who asks "should we use Grok for code?" gets an answer instead of a vibe.
