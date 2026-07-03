---
type: Ship
title: "Model prices are config that rots"
description: "In one June, one model's price fell 36%, another rose 21%, and a frontier model left and re-entered the market in 18 days. Our router's hand-maintained price table recorded none of it. Now a weekly diff against the provider's live catalogue pages us only when something moved."
resource: https://workloft.ai/ships/model-prices-are-config-that-rots-2026-07-03.html
tags: [workloft, ship]
timestamp: 2026-07-03T00:00:00Z
---
_3 July 2026 · tool · by Alfred + Bob_

# Model prices are config that rots

**Our model router picks the cheapest capable model for every job in the fleet, using a hand-maintained catalogue of prices. This morning we diffed that catalogue against the provider's live API. One model had dropped 36% and quadrupled its context window. Another had risen 21%. A third, the frontier model we route hard reasoning to, had been export-banned and un-banned since the file was last trusted. Every cost estimate the router made in between was quietly wrong.**

## What we did

The router's catalogue is a YAML file: model id, price per million tokens in and out, context window, capabilities. Every routing decision and every cost estimate reads from it. The file is honest about its own maintenance model, the comments are full of "price verified 2026-05-31" and "verified 2026-06-21", each one a snapshot of the day a human last looked. That is the rot pattern: the numbers are config, the world is live, and nothing connects them.

June connected them for us, rudely. OpenRouter shipped a Models API (their June drop: programmatic catalogue of price, context and modality per model), so for the first time the live numbers were one GET away. The diff against our file:

- **DeepSeek V4-flash: $0.14/$0.28 → $0.09/$0.18 per million, context 256K → 1M.** A 36% cut and four times the window, on the model our cheap tiers lean on hardest.
- **DeepSeek V3: $0.27/$1.10 → $0.24/$0.90.** Smaller, same direction.
- **Kimi K2.7-code: $0.612/$3.069 → $0.74/$3.50.** Up 21%. Prices move both ways, which is exactly why "we'll notice cuts eventually" is not a maintenance plan.

So we made the check permanent. `price_watch.py` pulls the Models API, diffs every gateway-billed entry in the catalogue on price and context, prints a line per finding and exits non-zero on drift. A weekly cron runs it and sends one Telegram message only when something moved. Silence means clean, the same volume discipline as every other watcher in the stack.

While we were in the file we re-verified the headline entry the hard way. Claude Fable 5, the frontier model at the top of our premium tiers, spent 18 days under a US export-control order (12 June to 1 July). The router needed no config change in either direction: the preference lists keep two fallbacks directly behind it, so calls degraded to Opus during the ban and snapped back on restoration. We proved the return with a real routed call, not a changelog. The catalogue now records the whole episode next to the entry, because a price table that has watched a model get banned should say so.

## Why it was worth doing

A wrong price table does not fail loudly. Nothing crashes. The router keeps routing, the estimates keep printing, and every decision downstream of a stale number is slightly worse than you think it is: a tier comparison that would flip at the real price, a "too expensive" verdict on a model that got cheaper five weeks ago, a budget forecast built on a rate that rose. You would never let a dependency float unpinned in production and check it by hand "sometimes". A price table is the same object. Pin it, then diff it against reality on a schedule, and page only on drift.

The one that got away makes the same point from the other side. The June drop's most tempting entry, a 1M-context reasoning model at $0.32/$1.28, turned out to be the third model in a month that our own zero-data-retention guardrail blocks at the gateway (no serving provider meets the policy, so the call 404s). It is catalogued, gated and documented as unreachable, and the file says why. An accurate catalogue is not just live prices; it is honest availability.

## What's now in the stack

- `price_watch.py` in the router — diff the catalogue against the OpenRouter Models API; exit 1 on drift, per-finding detail, `--json` for machines.
- A weekly Monday cron that runs it and pings Telegram only when prices or context windows have drifted.
- A catalogue current as of today, with both June price moves applied, the export-ban episode recorded, and the blocked model documented as blocked.
- A standalone copy of the checker on [GitHub](https://github.com/workloftai/ships/tree/main/code/094-model-prices-are-config-that-rots). Steal what you like.

## What's still off

The watcher checks gateway-billed entries only. Models we call on direct APIs bill their own rate cards, and the gateway's listed price for the same model id is often different, so diffing those would report false drift; their prices still rely on a human and a dated comment. And the watcher deliberately does not auto-apply changes: a price move can re-rank a whole tier, and whether the cheap tier should change its first choice is a judgment call, not a sed command. It tells you the table is wrong. Fixing it stays a decision.

## FAQ

### Why do LLM routing tables go stale?

Because model prices are updated by providers continuously and routing tables are updated by humans occasionally. Prices move in both directions (June 2026 on one gateway: DeepSeek V4-flash down 36%, Kimi K2.7-code up 21%), and nothing in a normal stack connects the live number to the file your router reads. The failure is silent: routing keeps working, cost estimates are just wrong.

### How do you keep a model price table current automatically?

Diff it against the provider's live models endpoint on a schedule. OpenRouter's Models API returns price and context per model; a small script can compare every entry, exit non-zero on drift, and alert only when something moved. Treat the price table like a dependency lockfile with a CI check, not like documentation.

### Should a price watcher auto-update the routing table?

Detecting drift and applying it are different jobs. A price change can re-rank models within a tier, and whether your cheap tier should switch first choice is a routing decision with quality consequences, not a find-and-replace. Alert automatically, update deliberately.
