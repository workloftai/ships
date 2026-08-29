# criticl — does a weak model's failures help a stronger one?

A port of the static [CritICL](https://arxiv.org/abs/2608.27455) idea: harvest
the mistakes a weaker model makes, distil them into a short critique, prepend
that critique to a stronger model's prompt, and see if it helps.

On our stack it did not. On the one task where our models had headroom (the digit
sum of a large power), the critique dropped the strong model from **44% to 28%**
over 25 problems. Five answers flipped right to wrong, one wrong to right. The
distilled critique was accurate, and describing the failure in detail seems to
have primed the strong model into it. Full numbers and the exact critique are in
[`result.json`](result.json).

## Two findings

1. **No headroom.** On standard reasoning tasks (word problems, number theory,
   combinatorics) both Gemini 2.5 Flash and Pro already scored ~100%. An
   inference-time booster has nothing to lift when the model already aces the
   task. We had to hunt for a task hard enough to separate them at all.
2. **Negative transfer.** On that harder task, the weak model's failure profile
   made the strong model worse, not better. Feeding a model a vivid description
   of how to fail can transfer the mistake, not the lesson.

## What's reusable here

- `gen_problems()` is a self-contained, dependency-free generator of the digit-
  sum-of-a-large-power task, with exact answers computed in code. Steal it as a
  hard eval where frontier models still have headroom.
- The harvest to critique to A/B design (`run()`) is the reusable shape: harvest
  failures, distil a static critique, then measure the target model with and
  against without it, scoring accuracy and output tokens.

The model calls go through our internal router (`from ruby import ruby`), so this
exact file will not run outside our box. Swap `ask()`'s body for your own
OpenAI/Anthropic/Gemini call and the rest is portable.

## The honest caveat

One task family, one model pair, 25 problems, temperature 0, static variant only.
This is not a verdict on the paper, whose gains were on other models and tasks. It
is a verdict on our attempt to make it pay on our stack, which failed, and did so
in an interesting direction.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
