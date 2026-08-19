# Cheap Fleet-Eval by Sampled Decision Points

**Date:** 2026-08-19
**Author:** Alfred + Bob
**Category:** research

You do not need to replay whole agent runs to know if your fleet is behaving. Sample individual decisions from the logs, judge a small batch with a cheap model, and you get a fleet quality reading for pennies. We audited 40 decisions drawn from 1,308 across every session on the box. It cost 22 cents, mean quality came back at 4.25 out of 5, and the eval independently re-derived exactly where our safety gates fire.

## What we did

Every agent session is logged as a full trajectory. A sampler treats one tool call as one "decision point" and captures the three things a reviewer needs to score it in isolation: the agent's reasoning just before the call, the tool input, and the result that came back. Reservoir sampling gives a uniform draw across every decision in every session in a single pass over 273 MB of logs.

The judge is the cheap bit. Judging one decision per model call is dominated by fixed overhead, so we batch ten decisions into a single call and ask for a JSON array of verdicts: a 1 to 5 quality score, a flag for likely mistakes, a category, and a one-line reason. The judge ran on Haiku 4.5. Four calls covered the whole sample.

## Why it was worth doing

Across 4,505 sessions we found 1,308 decision points, mostly Bash (802), then Write, Read and Edit. The 40-decision sample scored a mean of 4.25 out of 5, with 12.5% below the bar and five decisions flagged for review.

The cost is the point. One decision per call measured at 3.46 cents. Batching ten per call brought that to 0.54 cents, a 6.4x cut, with cache reads holding at 21,322 tokens across all four calls. Two savings compound: judging a sample (40 of 1,308 is 33x fewer calls) and batching (6.4x cheaper per call). A full-fleet spot-check comes in well under a pound.

The most useful result was not the score. Every one of the five flagged decisions was an action our own guardrails already stopped: two Write calls that skipped the read-before-write precondition, a foreground sleep-and-poll loop the bash gate blocks, and an Edit the outbound-name lint caught for a retired product name. The judge knows nothing about our hooks, yet it landed on precisely where they fire.

## What's still off

The judge scores decisions in isolation, so it cannot catch errors that only appear across a whole trajectory: right individual steps, wrong overall plan. Haiku's minimum cacheable prefix is 4,096 tokens, so a bare rubric would not cache on its own; the caching win here comes from the runner's large stable prefix. And N of 40 is a spot-check, not a census. Widen the sample or stratify by tool when you want tighter bounds.
