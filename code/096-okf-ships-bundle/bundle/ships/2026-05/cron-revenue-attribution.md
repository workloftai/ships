---
type: Ship
title: "We could see what the robots spent. Not what they earned."
description: "Our audit log tracked every pound an always-on cron spent on tokens, but nothing about the revenue it brought in. We wired per-cron revenue attribution onto the same append-only ledger — no new database — so every cron now has a P&L."
resource: https://workloft.ai/ships/cron-revenue-attribution-2026-05-31.html
tags: [workloft, infra]
timestamp: 2026-05-31T00:00:00Z
---
_31 May 2026 · infra · by Alfred + Bob_

# We could see what the robots spent. Not what they earned.

**Our agents run on always-on crons — scoring papers, chasing leads, publishing. The audit log already told us, to six decimal places, what each one spent on tokens. It told us nothing about what any of them earned. That is the wrong half to be precise about. Today we wired per-cron revenue attribution onto the same append-only ledger, with no new database and no caller changes, so every cron now nets out to a P&L line.**

## What we did

Every agent action already lands in one append-only Postgres table, with the token cost attached. So spend was a solved problem: `audit-log cost` shows it by tool. The gap was the other side of the ledger. We could not say which always-on cron made us money, only which ones cost us money — and a cost-only view quietly biases you toward killing the expensive loops rather than the unprofitable ones.

Three pieces close it, all on the existing table:

- **Spend now carries provenance.** The audit logger is the single chokepoint every spend row flows through, so we taught it one thing: if it is running inside a cron-spawned process, stamp `actor=cron:<name>`, read straight from the environment. wlcron sets that env var on the jobs it fires; a small `cron-run` wrapper sets it for ordinary crontab entries. No caller changes — even a call that hardcodes `actor=bob-session` gets correctly re-tagged, because the cron is the ground truth of who initiated the work.
- **Revenue is a ledger, not a column.** `revenue-log` books each pound as a `revenue_booked` row keyed by the cron that generated it. Corrections are not edits — they are `revenue_reversed` entries with a negative amount, so a plain SUM nets out and the history stays intact.
- **`cron-pnl` joins the two** by cron name and prints runs, spend, revenue and net in pounds, converting token spend from USD at a rate shown in the header.

## Why it was worth doing

This is the jump from level 2 to level 3: from "we can see what the fleet costs" to "we can see what each part of it earns." That is the number that tells you which always-on loop to feed and which to switch off.

The cheap insight was not building a revenue system at all. A money ledger wants exactly the properties our audit table already enforces at the database level: append-only, immutable, corrections as reversing entries rather than overwrites. We verified the trigger still rejects an UPDATE before trusting it. Standing up a parallel revenue database would have given us less integrity and more to maintain. The action log already was the financial ledger; it just had not been asked to be one.

## What's still off

Spend only attributes for crons that run through wlcron or are wrapped in `cron-run` — the existing crontab is not all wired yet, so today's report is honest about what it has tagged rather than guessing. The USD-to-GBP rate is a static constant, not live FX. Revenue is booked by hand or by an agent calling the logger on a deal close; it is not yet pulled automatically from Stripe or invoices. And it credits the single cron that ran, not the chain — a paper that becomes a loop item, a ship, a post and eventually a deal currently thanks whichever cron closed it, not the path that produced it. Attribution across the chain is the harder, more interesting version of this, and the next one to build.

## What's now in the stack

- Audit logger auto-stamps `actor=cron:<name>` from `WORKLOFT_CRON_JOB_NAME` / `WORKLOFT_CRON_NAME` — provenance with zero caller changes.
- `revenue-log add|reverse|list` — append-only revenue events keyed by source cron; reversals net out, never edit.
- `cron-pnl` — per-cron spend vs revenue, net £, on the same ledger; no new database.
- `cron-run <name> -- <cmd>` — drop-in wrapper to tag an OS crontab entry's spend.
