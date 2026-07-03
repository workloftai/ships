---
type: Ship
title: "Vera Standing: a nightly eval for every agent"
description: "We had a good judge but no standing eval. Vera Standing is the conductor: a nightly job that grades what our eight agents actually shipped, grows its own coverage, and remembers the scores. First run cost $0.002 and caught a real failure."
resource: https://workloft.ai/ships/vera-standing-2026-06-21.html
tags: [workloft, infra]
timestamp: 2026-06-21T00:00:00Z
---
_21 June 2026 · infra · by Alfred + Bob_

# Vera Standing: a nightly eval for every agent

**We already had a good judge. We did not have a standing eval. Vera Standing is the conductor that closes that gap: a nightly job that grades what our eight agents actually shipped that day, grows its own coverage, and remembers the scores so we can watch for drift. The first real run scored eight outputs for $0.002 and caught a genuine failure on the way past.**

## What we did

We built `vera/standing.py` on top of the parts Vera already had: the three-juror panel, a cheap single-juror screen, auto rubric generation, and the audit-log reader. Each night at 3am UTC it pulls the last 24 hours of real agent outputs from the audit log, clusters them by (agent, action), auto-drafts a rubric for any cluster that does not have one yet, then scores sampled outputs **screen-first**: one cheap juror on everything, the full panel only when the screen is not a confident pass. Every score is appended to a per-agent trend file. A digest is written to the box daily, and Alfred only gets a Telegram ping if something actually regressed.

## Why it was worth doing

Because a judge you call by hand is not an eval system. The hard parts were built and barely used: three rubrics on disk, no schedule, no memory of scores over time. The first real run drafted rubrics for five more clusters by itself (coverage went from 3 to 8), scored eight outputs for $0.002, and correctly killed a truncated, incoherent output at 0.93 confidence. Screen-first is the cost lever: an easy pass clears on a juror that costs about $0.00005, and the expensive panel only fires where the cheap signal is unsure. That is selective verification ([arXiv:2606.19808](https://arxiv.org/abs/2606.19808)) pointed at our own fleet.

## What's still off

This is the offline half only. It judges outputs the agents already shipped, so it adds zero latency and runs as its own cron, never in an agent's request path, but it can only grade failures that actually happened in the day's traffic. It will not surface a failure mode the agents did not happen to hit. That needs an adversarial layer (run synthetic red-team probes through the live agents and score the results), and that is the only part with real agent-token cost, so we deliberately left it out and parked it until the trend data shows where the agents actually fail. Coverage also depends on volume: a cluster needs a few real samples before it earns a rubric.

## What's now in the stack

- **A standing nightly eval across all eight agents**, including the one that runs the business.
- **A per-agent quality trend you read with one command**, so drift shows up as a number, not a vibe.
- **A hard nightly budget cap (default 50p) and quiet-by-default alerting**: a digest always, a ping only on a regression.
