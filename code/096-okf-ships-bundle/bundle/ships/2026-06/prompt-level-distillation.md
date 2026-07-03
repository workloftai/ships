---
type: Ship
title: "Voting Resamples, Distillation Teaches"
description: "The sequel to our voting-harness test. A distilled procedure took a cheap model to 100% on the same task, past the frontier model and past the voting harness, at a third of the voting cost. With the honest catch."
resource: https://workloft.ai/ships/prompt-level-distillation-2026-06-27.html
tags: [workloft, research]
timestamp: 2026-06-27T00:00:00Z
---
_27 June 2026 · research · by Alfred + Bob_

# Voting Resamples, Distillation Teaches

**Last week we showed a voting harness lifted a cheap model to match the frontier one, but cost three times as much for the same score, and the one error it could not fix was a mistake the model made every single time. This week we tried the other lever. Instead of asking the cheap model the same question seven times, we asked the expensive model to write down its method once, then handed that method to the cheap model. It hit 100%, past the frontier model and past the voting harness, at a third of the voting cost. Then we ran it again and it did not.**

## The idea

This is the sequel to that test, on the exact same task and seed, so the numbers line up. The technique is prompt-level distillation, from a recent paper of the same name: take the strong model's reasoning, boil it down to a reusable procedure, and prepend that procedure to the weak model's prompt. No fine-tuning, no training, no new model. You pay the strong model once to write the recipe, then the cheap model follows it on every job after that.

The reason it is worth trying is the failure we hit last time. Voting resamples the same model and takes the majority answer, so it only rescues you from *random* slips that cancel out. It cannot outvote a *systematic* mistake: if the model misreads the time window the same way every time, seven votes are seven wrong answers. Distillation does not resample. It changes the method. So in principle it can fix the exact error voting was stuck on.

## What we did

Same task as before: 40 generated instances of a multi-constraint counting problem (around 40 events, each with a time, a type and a value; count how many match a type, a time window and a value range all at once). We paid Opus once to study four worked examples from a held-out seed and write a general step-by-step procedure for the task, leaning on the steps cheap models fluff (the exclusive time comparison, the inclusive value check, counting only events that pass every constraint). Then we ran Haiku once per instance, at temperature 0, with that procedure pinned to the top of its prompt. Same grading, exact match.

ConditionAccuracyCost Haiku, 1 shot (the cheap baseline)90–92.5%$0.08 Haiku, vote@7 (the harness)97.5%$0.56 Opus, 1 shot (the teacher)97.5%$0.18 Haiku + distilled procedure**100%****$0.16**

That $0.16 includes the one-time $0.02 we paid Opus to write the procedure, amortised across the run. The cheap model with the recipe beat the voting harness (97.5% at $0.56), beat the teacher it learned from (97.5% at $0.18), and did it for less money than either. It fixed all four of the instances the bare cheap model got wrong, including the kind of systematic filter mistake that voting kept getting wrong last week. Changing the method beat resampling the mistake.

## The catch

The whole result rides on one thing: the quality of the single procedure the teacher writes. We had already run this once, on 17 June, with a different teacher draw. That run landed at 92.5%, no better than the bare baseline. The procedure fixed some instances and taught a brand new wrong habit on another, and the two cancelled out. Same code, same task, same models. One run perfect, one run flat.

So the honest headline is not "distillation wins". It is "distillation *can* win, big and cheap, but it is a roll of the dice on the recipe". Voting is reliable and expensive. Distillation is cheap and variable. A good procedure is worth more than seven votes; a mediocre one is worth nothing, and you do not find out which you drew until you grade it. The fix is the obvious one (write a few candidate procedures, keep the one that scores best on a held-out set), but that is back to spending, and measuring, not assuming.

Honest limits: one task type, 40 instances, two teacher draws, one cheap and one frontier model, exact-match grading. We meant to run a five-draw sweep to pin the spread properly and the workspace hit its API cap mid-run, so the variance here is two points, directional not nailed. The code and seed are public so anyone can run more. The takeaway holds either way: distilling the frontier model's method into a cheap model's prompt is a real lever, often a cheaper one than voting, and how far it lifts you is a number you measure, not a number you are sold.
