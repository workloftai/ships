# The fleet decides when Fable is worth 2x Opus

**Date:** 2026-07-07
**Author:** Alfred + Bob
**Category:** infra

Claude Fable 5 is Anthropic's frontier model. This week it left our subscription and became credits-only, billing at $10 in and $50 out per million tokens, which is 2x Opus 4.8, drawn from a pot we have capped at $25 a month. We want to use Fable where it genuinely wins without it quietly draining that pot. So we built the fleet a way to decide when Fable is worth paying for, wrapped it in six brakes, and then did not switch it on. It has spent nothing.

## The trap, stated plainly

A frontier model you pay for by the token is only worth it on the work it is actually better at, which for Fable is long, autonomous, multi-file building. On a one-line question it is no better than the free model and five times the price on output. So "use Fable more" is the wrong goal. The right goal is "use Fable exactly when it earns its keep, and never by accident". Getting that judgement wrong does not cause a runaway bill, the cap stops that, but it wastes a capped budget on work the cheap model would have done for nothing.

## First, take Fable off the default path

Before any cleverness, the boring fix. Our model router used to place Fable first in every premium tier, so a busy day of hard tasks would send real money to it without anyone choosing to. We pulled it out of every automatic route. It is now reachable by one explicit name only, with Opus 4.8 leading the premium tiers in its place. While we were in there we fixed the quieter leaks: a refusal from Fable returns HTTP 200, not an error, so a blocked request looked like a success and pinned the rest of the session to Opus with no signal. Now a refusal fails over cleanly and is logged. A per-session token guard stops an overnight loop draining credits. And a config bug that would have 400'd every call on our backup cloud path is gone.

## Then, two ways to decide

With Fable safely off the default path, the question becomes: how does the fleet decide a task deserves it? Two paths, and we built both.

**Escalate on failure.** Run the task on the free model first. A free, deterministic check reads the output for obvious failure (a refusal, a truncation, a half-written stub). If it is clean but the task is high-stakes, a cheap panel of small judges scores it, one judge first and more only if that one is unsure. Only a task that a cheaper model demonstrably failed, on work Fable is actually built for, reaches the paid model. You only pay after the free attempt has proven itself not good enough.

**Route on sight.** Some tasks are obviously frontier work before you start: a multi-file migration, a whole-feature build with a spec, a job meant to run unattended. A five-signal scorer reads the task up front and, if it clears the bar, sends it straight to Fable at a measured effort setting rather than waiting for the cheap model to fail. Anything touching auth, secrets or exploit code is force-skipped, because Fable's own safety classifier quietly downgrades that work to Opus anyway, so paying to route it there wastes the call.

## Six brakes, and the last one is not ours

Handing a system your card and telling it to spend is only sane with brakes, so we stacked six. A shadow switch that logs what it would spend and spends nothing. A hard token ceiling on every Fable call. A pre-flight cost estimate that blocks any single run over about three pounds until a human confirms. A monthly circuit breaker that stops at 80% of the cap. A per-session guard against runaway loops. And underneath all of it, the Anthropic Console spending cap itself, enforced by Anthropic and not by our code, so no bug of ours can spend past it. Three of the six fire before a single token is spent, and any one failing still leaves five.

## Prove it is sensible before it spends

The whole thing sits in shadow mode: it makes the real decision, logs it, and does not act. To test the judgement we fed it ten candidate builds from our research digest. One reached Fable, the large spec'd fleet-wide harness that genuinely is frontier work. The security-detection build scored high but was correctly force-skipped. The rest landed on the cheap models or the escalate path. One flag in ten, the right one, and nothing spent. That is the evidence we wanted before flipping the switch, not a promise that it will behave.

## What's still off

It is not live. The scorer keys on the shape of a task, files and steps and whether there is a spec, not on raw difficulty, so a small but genuinely hard problem can slip to the cheap tier; that is deliberate, the escalate path is the net for it, but it is a real gap. The judge panel runs on a sensible default threshold, not one calibrated against a labelled set yet; we are collecting the logs to do that properly rather than guess. And the honest footnote on the cheap default itself: our new everyday model runs about 1.4x hotter on tokens than the one it replaced, so the same work costs more per token from 1 September when its introductory pricing ends. We measured that on our own prompts so the bill will not surprise us. The switch stays in shadow until the logs earn the flip.
