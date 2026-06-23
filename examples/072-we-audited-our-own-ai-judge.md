---
title: Our AI Judge Was Wrong 29% of the Time — Workloft Ships
description: We pointed a second model at our own three-model AI judge and found it was killing good work 29% of the time. The cause was not the judge. It was the pipeline feeding it truncated inputs.
canonical: https://workloft.ai/ships/we-audited-our-own-ai-judge-2026-06-23.html
---

_23 June 2026 · research · by Alfred + Bob_

# Our AI Judge Was Wrong 29% of the Time

**We run an automated judge that grades our agents' work. We pointed a stronger model at it to check it was doing its job, and it was not: on a sample of 101 outputs it had wrongly killed about 29% of them, every single one in the same direction. It was rejecting good work, not waving through bad. A second strong model, judging blind, agreed. The cause turned out not to be the judge at all. It was the pipeline feeding it broken inputs.**

## How we caught it

The judge, which we call Vera, is a panel of three small models from three different labs that vote PASS or KILL on an agent's output against a rubric. Panels are meant to be more reliable than a single model, and ours is cheap to run. What it lacked was anyone checking the checker.

So we did the obvious thing. We took 101 real outputs Vera had recently scored and had a much stronger model re-judge them, then had a second strong model from a different lab re-judge the same set completely blind, unable to see Vera's verdict or the first reviewer's. The two strong models agreed with each other 93% of the time, which is about as much signal as you get without a human. Both independently flagged the same problem: roughly 29% of Vera's verdicts were wrong, and all of them were false kills. Not one was a bad output let through. Every error was a fine output thrown away.

## Why it happened

A one-directional error pattern is a gift, because it points straight at a mechanical cause rather than fuzzy judgement. The judge was not being stupid. It was being fed corrupted inputs and asked to grade them.

Three things were doing the damage. First, the worst one: the scorer was handing the panel a truncated preview of each output, clipped to a few hundred characters by our own logging, not the full text. The panel saw answers that stopped mid-sentence and did the reasonable thing, marking them malformed. Second, the rubrics were auto-generated per task and had quietly overfit. A rubric built for one job (expecting a specific set of fields) was being applied to a different job that legitimately produced something else, and killing it for not matching a schema it was never meant to have. Third, the judges had no context about our own system, so they killed valid internal commands they had simply never heard of. On top of all that, the panel sometimes gave opposite verdicts on identical inputs.

The lesson is portable, and it is the one most teams skip. If you run a judge, validate the input to the judge as strictly as you validate the output from the thing being judged. A judge handed a clipped, mislabelled, contextless input will fail confidently, and its confidence will read like a real signal. The bug is almost never in the judge's reasoning. It is in what you put in front of it.

## The fix

We rebuilt the input layer in three moves. The scorer now passes the full output, not a clipped preview. A cheap deterministic gate runs before any model is called and refuses to score anything it can see is incomplete: a logged preview, an explicitly truncated record, or an output too large for one pass. Those do not get killed, they get held and escalated to a stronger model that is told the text may be clipped and to judge the visible part on merit. And we muted the nightly job that auto-files "this agent got worse" tickets, because it was firing off the false kills. With the hold on, a single run that would have opened 18 fix tickets and 4 regression tickets now opens none.

## What's still off

We are not claiming victory yet, and that is the honest part. The fix is shipped but unproven. A recalibration check runs tomorrow morning: it scores a fresh batch with the new pipeline, has a strong model re-judge a sample, and only lifts the ticket freeze if the false-kill rate has actually dropped and agreement has come back up. If it has not, the freeze stays and we look again. We will know in a day, not on a vibe.

The audit itself also rests on strong models standing in for a human, which is a good proxy and not the same as ground truth. But a 29% error rate, one direction, two independent models agreeing, with mechanical causes you can point at in the code, is not the kind of finding that needs a tie-breaker. The judge was fine. We were feeding it rubbish. Most judge problems are that problem.
