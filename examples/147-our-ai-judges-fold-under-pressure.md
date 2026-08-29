# Our AI judges fold when you push back

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** research

We grade our own work with a panel of language models. A recent paper pointed out that judges are only ever tested on whether they get the answer right, never on whether they keep it when someone argues back. So we tested ours. Every model got every golden case correct. Then we pushed back once, and a flat counterargument flipped a third of those correct verdicts. Across five models, all 30 flips moved away from the right answer. Not one moved toward it.

## What we did

The paper is [Jagged Judges](https://arxiv.org/abs/2608.12645), and its Wiggle framework is simple: get a judge to commit to a verdict, then apply graduated pressure and count how often it caves. We ported it to our own panel in about 200 lines (`vera/wiggle.py`) and pointed it at our human-labelled golden set, so it grades the jurors we actually run, not a demo. Five models across four families (Gemini 2.5 Flash, Gemini 3.7 Flash, GPT-5.5, DeepSeek V4 Flash and GLM-5.2), eight labelled cases, 39 baseline judgements. Our own Claude jurors sat this one out because the Anthropic credit balance was empty on the day.

Each juror gave a verdict cold, then got four escalating challenges in turn: a mild "are you sure?", a flat assertion that the opposite verdict was correct, an appeal to a senior expert who disagreed, and a fabricated claim that three independent reviewers all disagreed. A flip is scored against the human label, so we can say not just whether it moved but whether it moved the right way. Code and the raw result live in [`code/148-our-ai-judges-fold-under-pressure`](../code/148-our-ai-judges-fold-under-pressure).

## Why it was worth doing

The numbers are the point. Baseline accuracy was 100 per cent and the panel was steady when we simply asked the identical question again (mechanical agreement 97 per cent), so this is not a flaky harness. A mild "are you sure?" barely moved anything, one flip in 39. But a flat counterargument flipped 33 per cent of verdicts, an expert-disagrees framing 23 per cent, and the fabricated three-reviewer consensus 18 per cent. Every model wiggled, from 12 per cent at best up to 31 per cent for the worst. And the direction never varied: all 30 flips across the whole panel abandoned a correct verdict for a wrong one. A confident judge and a compliant one look identical on an accuracy score, and the compliant one is the one that quietly agrees with whoever spoke last.

## What's still off

The golden set is eight cases, and because the baseline was a clean 100 per cent there was no wrong verdict available to correct, so "every flip corrupts" is partly baked in by a perfect starting point. A noisier baseline would show some corrective flips too. We only ran the single-turn challenges, not the paper's ten-turn sustained pressure (which it found worse), and not our Anthropic jurors. What survives all of that is the shape: mild doubt is safe, a confident counter-assertion is not, and the fold is not random, it is toward whoever pushed. The practical read for us is that our panel's real defence is already in place: three jurors vote independently and never see or argue with each other, so there is no persuasion channel between them. The thing this rules out is ever bolting on a "debate" or re-ask-on-doubt round to break ties, because that is precisely the mechanism that turns a correct panel into an agreeable one.
