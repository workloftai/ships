# A weak model's mistakes made a smarter one worse

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** research

There is a tidy idea doing the rounds: take the mistakes a cheaper model makes, distil them into a warning, and hand that warning to a stronger model so it sidesteps the same traps. We built it and tested it on our own stack. On the one task where our models had any room to improve, the warning did not help the strong model. It dropped it from 44% to 28%. It primed the model into the very mistakes it was told to avoid.

## What we did

The idea is from a paper called [CritICL](https://arxiv.org/abs/2608.27455). We ported its static variant in about 200 lines: run a weaker model over a set of problems, collect the ones it gets wrong, distil the recurring failure patterns into a short critique, then prepend that critique to a stronger model's prompt. Weaker model was Gemini 2.5 Flash, stronger was Gemini 2.5 Pro (our Anthropic models were credit-blocked on the day).

The first thing we hit was a wall worth reporting on its own. On every standard reasoning task we tried, word problems, number theory, combinatorics, both models already scored around 100%. There was no headroom for any inference-time trick to work with. We had to hunt for a task hard enough to separate them, and found one: the digit sum of a large power, where a model must compute something like 9 to the power 24 exactly and add the digits. That, they cannot do reliably in their heads. Code and the raw result live in [`code/149-weak-model-mistakes-guide-a-smarter-one`](../code/149-weak-model-mistakes-guide-a-smarter-one).

## Why it was worth doing

On that task, over 25 held-out problems, the numbers came out backwards from the promise. Flash scored 12%. Pro on its own scored 44%. Pro with the critique built from Flash's failures scored 28%, a 16-point fall. Five answers flipped from right to wrong once the critique was added, and only one flipped the other way. It was not overthinking either: the critique run used 16% fewer output tokens.

The likely cause is the interesting bit. The distilled critique was accurate. It correctly said the weaker model loses precision on large powers and mangles the final digit sum. But describing a trap in detail to a model that was not going to fall into it seems to work like priming: you put the failure mode front of mind, and the model steps toward it. Feeding a weaker model's mistakes to a stronger one does not always transfer a lesson. Sometimes it transfers the mistake.

## What's still off

We are not claiming the paper is wrong. This is one task family, one model pair, 25 problems, temperature zero, and only the static variant, not the per-input dynamic one. Our task is arithmetic execution, not the reasoning traps the method was aimed at, and the critique was distilled by the strong model itself. The honest headline is narrow: on our stack we could not make CritICL pay, and in the one fair test we could construct, it backfired. What generalises is two working assumptions. Check your model is not already at the ceiling before you bolt on a booster, or you pay tokens for nothing. And be wary of handing a model a vivid description of how to fail, because it may take you up on it.
