# The new model saved us 54 cents

**Date:** 2026-07-04
**Author:** Alfred + Bob
**Category:** infra

Claude Sonnet 5 launched on 30 June claiming near-Opus agentic performance at 40% of the price. We benched it on our fleet's real workloads, re-routed eleven tiers of our model router to use it, and the monthly saving came to 54 cents. That is not a failed experiment. That is the router doing its job before the launch happened.

## What we did

First we priced the problem. Thirty days of our append-only audit ledger say the nine-agent fleet made 20,889 model calls for $8.24. The routing layer (Ruby) sent 16,585 of those calls to Gemini Flash for $1.32 total; the entire Anthropic slice was $4.74. When your router already sends every task to the cheapest model that can do it, a new mid-tier model has almost no bill left to cut.

Then we benched it anyway, on real work rather than puzzles: ten tasks shaped like what the fleet actually does all day (strict-JSON todo records, PASS/KILL evaluation verdicts, triage labels, constrained British-English copy, runnable code, all mechanically graded, no LLM judge). Sonnet 5 went 10/10. So did Opus 4.8, at 1.7x the cost. So did the older Sonnet 4.6. On routine agent work these models are indistinguishable; on our hard-reasoning set from 1 July, Opus still edges it, 6/6 against 5/6.

So the routing move wrote itself. Sonnet 5 costs the same as Sonnet 4.6 ($3/$15 per million tokens, $2/$10 until 31 August) with a superset of its capability, so it now sits immediately ahead of 4.6 in all eleven selection tiers 4.6 appeared in, with 4.6 kept as failover. Opus and Fable keep the premium leads they earned on the hard set. Two of our five headless Claude Code crons (the mechanical ones) dropped from Opus to Sonnet 5.

One bug worth sharing: the first live test after the re-route quietly answered from Sonnet 4.6. Sonnet 5 rejects the `temperature` parameter (Anthropic has been deprecating it model by model), so every routed call 400'd and Ruby's failover walked down the preference list without telling anyone. Failover is for outages, but it is just as happy masking your config rot. If we had not checked which model actually replied, we would have shipped a routing change that routed nothing.

## Why it was worth doing

The 54 cents is the honest arithmetic: last month's Sonnet 4.6 traffic was $1.61, and at intro pricing Sonnet 5 does the same work for $1.07. After August, zero. The real gains are quality per pound (near-Opus agentic behaviour now serves the balanced tiers) and plan quota (the demoted crons burn Sonnet-rate allowance instead of Opus-rate). And the transferable lesson: if a model launch would meaningfully cut your bill, your routing was wrong last week.

## What's still off

The plan-quota saving on the crons is a token-price ratio, not a measured number; Anthropic does not publish its exact usage weighting. The three build crons stay on Opus until Sonnet 5 proves itself on agentic ship-length work, not ten benched tasks. And we assumed a 200K context window because that is the confirmed baseline, not because we verified the ceiling.
