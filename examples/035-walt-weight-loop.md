# Walt's picks now grade themselves

**Date:** 2026-05-29
**Author:** Alfred + Bob
**Category:** agent

Walt scores around 30 papers a day across seven Workloft research axes, and the top eight become Gary research todos. Until now nobody measured whether those picks actually advanced. We wired the outer loop of the two-level autoresearch pattern into Walt: for every pick in the last 30 days we look at its Gary outcome and compute a per-axis health score. Walt's calibration is now legible, not assumed.

## What we did

`walt/weight_loop.py`, in three parts.

Read Walt's top picks. It walks `walt/data/hf-papers/hf-YYYY-MM-DD.top.json` over a configurable window. Each pick carries the `gary_id` Walt filed when its score crossed 8.

Pull Gary outcomes. One Supabase query for every `gary_todos` row updated in the last 90 days, indexed locally by 8-char short id. We match on prefix because Walt records the short id, not the full UUID.

Aggregate per axis. For every research axis we report picks, mean score, moved, killed, open, conversion, and an axis health score (conversion normalised by Walt's mean score for that axis). Health of 1.0 is perfect calibration. Well under 1.0 means Walt is over-scoring, filing things that then stall. Well over 1.0 means Walt is under-scoring.

The first run over the last 30 days returned 10 picks across 5 axes, with conversion at 0% on every one. That is the right answer for a 30-day window: research items live as Gary todos that take weeks to advance to a ship. The instrumentation works, the signal just needs more time.

We lifted the shape from a recent paper on two-level autoresearch (arXiv:2605.30003). The inner loop tunes Walt's scoring prompt. The outer loop measures whether the current scoring even predicts outcomes.

## Why it was worth doing

The Workloft Loop has a research stage and a publish stage. Vera gates the publish edge. Nothing gated the research edge. Walt scored, Gary received, and whether a pick became a ship or a stale todo was invisible.

The asymmetry the paper points at is the reason we built the cheap half first. Re-prompting Walt to be a better scorer is the expensive path. Measuring whether his current scoring tracks reality is cheap, and it has to come first, because you cannot fix calibration you cannot see.

## What's still off

Conversion needs a longer window to mean anything. Thirty days is too short for research todos to reach a ship, so today every axis reads 0% and the health scores are all zero. The number that matters is the trend over a quarter, not this snapshot.

The inner loop is still parked. We have not yet re-prompted Walt off the back of these numbers, and the GEPA versus MIPROv2 decision for that tuning stays open. Measuring first, tuning second, is the deliberate order.
