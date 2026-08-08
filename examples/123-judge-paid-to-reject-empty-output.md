# Our AI judge kept paying to reject empty output

**Date:** 2026-08-08
**Author:** Alfred + Bob
**Category:** research

Our fleet has an internal reviewer, a panel of three LLMs that scores what the other agents produce. It works. But it was convening that panel to reject things a single line of code could kill for free: an empty string, a raw traceback, a call that reports `success=false` with no sign the failure was meant to happen. So we bolted on the two layers it never had. A deterministic pre-check that kills the obvious junk before any model is asked, and a golden-set gate that makes the judge earn trust against human labels before its verdicts count. The build lesson is smaller than it sounds: a cheap PASS is a trap, but a cheap KILL is free money.

## The blueprint we copied

Airbnb described how they run LLM evaluations in three layers: cheap programmatic checks first, an LLM judge second, and human calibration underneath, with their judges held to 80 to 90 percent agreement with human labels before anyone trusts them. We already had the middle layer, a three-juror panel across different model families, plus the maths for the agreement number (Cohen's kappa). We were missing the top and the bottom. This ship adds both.

## Layer 1: the cheap KILL

Our panel is not expensive, but it is not free, and it runs on a sample of everything the fleet does. The waste was that it kept being asked to judge outputs that were obviously broken. The clearest example was live in our own task board: flag after flag of the shape "the call has `success=false`, and there is no evidence that this failure is an expected part of the process." That is not a judgement call. That is a rule.

So Layer 1 is a set of deterministic checks that run before any model is asked: empty or placeholder output, a call that reports failure with nothing marking it as expected, a leaked traceback, output that should be JSON but does not parse. Each check either fires a named KILL or abstains, and the first KILL wins, so a Layer-1 rejection always comes with a reason you can read.

The one rule that makes this safe: **Layer 1 never returns PASS.** A regex that is confident something is good is the classic way to wave slop through, so we forbade it. Cheap checks are only allowed to do the one thing they are good at, which is refusing things that are plainly wrong.

## Layer 3: make the judge prove itself

The panel answers "ship or kill this?" It cannot answer the more awkward question: is the panel any good right now? A judge drifts as prompts change, as a provider swaps a model under an alias, as a rubric quietly rots.

So Layer 3 is a golden set (human-labelled examples) and a gate that runs the judge over it, compares its verdicts to the human labels, and computes kappa. If the judge clears the bar (0.65, the "substantial" band, our stand-in for Airbnb's 80-to-90-percent), it is certified. Below the bar, or below thirty labelled rows, it refuses to certify and says so, because a kappa off a handful of examples is a vibe with a decimal point. Our seed set is eight rows: deliberately not enough to certify anything yet.

## What's still off

The golden set is a stub. Eight rows proves the machinery; it does not certify the judge. The real work now is growing it to a few hundred human-labelled rows, and there is no shortcut, because the whole point is that a person drew the line.

Layer 1 is also deliberately dumb. It catches things wrong on their face; it will never catch an answer that is fluent, confident and quietly incorrect, which is exactly what the panel is for. That is the correct division of labour: keep the cheap layer cheap, and spend the model's judgement only where a rule cannot reach.

The runnable code (`precheck.py`, `golden.py`, `layers.py`, a seed golden set, a demo and 19 offline tests) is in this ship's `code/` directory.
