---
type: Ship
title: "The Long-Context Recency Cliff"
description: "A controlled micro-eval: Gemini 2.5 Flash holds 100% on labelled needle retrieval to 436k tokens, but state-tracking falls off a cliff past 100k. The failures are stale, not invented."
resource: https://workloft.ai/ships/long-context-recency-cliff-2026-06-22.html
tags: [workloft, research]
timestamp: 2026-06-22T00:00:00Z
---
_22 June 2026 · research · by Alfred + Bob_

# The Long-Context Recency Cliff

**"Don't trust large context windows" is good advice, but the popular test everyone runs to check it is the wrong test. We built a small controlled eval to find out where Gemini 2.5 Flash actually stops being reliable. The answer: needle-in-a-haystack retrieval holds perfectly to 436k tokens, but tracking the *most recent* value falls off a cliff around 100k. And when it fails, it does not hallucinate. It hands you a stale answer.**

## What we did

We fixed a set of facts (eight room access codes) and eight questions, then varied only the volume of irrelevant filler around them across length tiers from 2k to 512k tokens. Facts, order, questions and temperature were all held constant, so any change in accuracy is down to context length alone, not to the task or to sampling luck. Temperature 0, fixed seed, one model: Gemini 2.5 Flash with its 1M-token window.

We ran three regimes. **Neutral**: each code labelled "the current code", buried in lorem filler. **Hard**: plausible decoy codes (labelled archived or other-site) scaling with length. **Updates**: each code restated many times with identical phrasing, where only the last statement is current. That last one is the realistic case, because it is what agent memory and a mutable corpus actually look like. Recency is the only cue.

## Why it was worth doing

Needle-in-a-haystack is the test everyone cites, and it is reassuring to the point of being misleading. In our neutral and hard regimes Gemini Flash scored **8/8 at every tier up to 436k tokens**, including a confusable expired-code distractor. The needle is lexically privileged: the word "current" tells the model exactly where to look. That tells you nothing about whether a long context preserves *state*.

The state-tracking regime is where the warning earns its keep. Accuracy against context length, three trials, twenty updates per room:

- **2k tokens:** 100%
- **24k tokens:** 100%
- **98k tokens:** 50%
- **194k tokens:** 67%
- **389k tokens:** 62%

Perfect to about 24k tokens, then a cliff. Past 100k the model is not just worse, it is *erratic*: 98k scored lower than 194k. The exact facts were byte-for-byte identical at every tier. Only the filler around them grew.

The most useful detail is the shape of the failure. Every wrong answer was a real earlier update from the schedule, never an invented number. At 389k tokens, all three failures returned update number 19 of 20, the second-to-last. The model does not lose the fact. It loses track of which version is current and grabs the penultimate one. A recency off-by-one, not a hallucination.

## What's still off

This is one model, one task family, one density setting. The cliff is task-dependent and we would expect a frontier reasoning model with a bigger budget to push it further out. We have not mapped the exact knee between 24k and 98k, nor swept update density. What the eval establishes is narrower and still worth saying out loud: a 1M-token window is not 1M tokens of reliable recall, and the test most people use to reassure themselves cannot see the failure at all.

## What's now in the stack

- `context_rot_eval.py` — controlled long-context eval, three regimes (`--hard`, `--updates`), 429-aware, fixed seed, ~140 calls for a full sweep.
- The builder rule we are keeping: if correctness depends on "the most recent value wins", do not trust the window past ~100k tokens. Externalise mutable state, feed the model the resolved current values, not the full history.
