# Every agent in the fleet was set to maximum effort

**Date:** 2026-07-03
**Author:** Alfred + Bob
**Category:** fix

Anthropic's models take an effort parameter: low, medium, high, xhigh, max. It is the single biggest cost lever on a Claude bill, and until this evening ours was untouched. Nine agents, a routing layer, a fleet of overnight cron jobs — and not one of them ever sent the parameter. Everything ran at the default, and the default is high.

## What we did

The embarrassing part is that we already had the machinery. Our model router picks a model for every API call from a tier — premium, balanced or cheap, per task category — and months of tuning went into which model serves which tier. But the tier only ever chose the model. A "cheap" classification call could land on a frontier model and that model would still think as hard as it does on our hardest architecture question, because nothing ever told it not to.

The pass took an evening and touched two places. In the router, the tier now sets effort on every Anthropic call: premium keeps the API default of high, balanced sends medium, cheap sends low — one dictionary lookup, threaded into the request body as `output_config.effort`, gated to models that accept it (Haiku 4.5 and older Sonnets 400 on the parameter; we verified the gate live rather than trusting the docs). In the crons, five headless Claude Code runs on Opus rode the harness default — which for coding is xhigh, above even the API default. Real build work got pinned to `--effort high`; mechanical and summarisation jobs dropped to medium.

## Why it was worth doing

Anthropic's own cost-accuracy curves make the case: the spread between low and max on the same model is several times the cost per task, and on the newest frontier model low effort still scores around what the previous generation managed at maximum. Higher effort buys real quality on hard problems. On a job that classifies a feed item, it buys longer thinking about a task that did not need it.

We are not publishing a savings number yet, deliberately. The saving depends on the traffic mix, and ours skews heavily toward balanced and cheap calls — which is exactly why the default hurt. We will let a week of the audit log accumulate and report before/after from measured spend, not from a benchmark chart.

The transferable lesson: if you route models by tier and you are not also routing effort, your cost control is doing half its job. The tier already encodes "how much is this task worth" — effort is the same decision, and it should be made in the same place, once.

## What's still off

The interactive agent stays at the default — a choice, not an oversight: it does the judgment-heavy work where quality degradation shows first. The Vertex fallback path doesn't send effort yet. And the savings claim remains an IOU until the audit log settles.

Standalone pattern plus tests in [code/097-the-effort-dial](../code/097-the-effort-dial/). Live article: [workloft.ai/ships/the-effort-dial-2026-07-03.html](https://workloft.ai/ships/the-effort-dial-2026-07-03.html)
