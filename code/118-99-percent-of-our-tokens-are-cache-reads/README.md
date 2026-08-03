# fleet-cost

What our Claude Code usage actually costs, read from the logs Claude Code
already keeps. No third-party tool, no telemetry, nothing leaves the machine.

Ship write-up: `examples/118-99-percent-of-our-tokens-are-cache-reads.md`

## Why

We run a lot of Claude Code and had no clean view of the spend by day, model, or
workspace. Rather than run an unaudited third-party tracker over session logs
full of secrets and client data, we read the data ourselves: every assistant
turn in `~/.claude/projects/**/*.jsonl` carries its own model and token usage.
This just adds it up and applies the published prices.

## Run it

```bash
python3 fleet_cost.py                 # last 30 days, by day
python3 fleet_cost.py --days 7        # last 7 days
python3 fleet_cost.py --by workspace  # group by workspace
python3 fleet_cost.py --by model      # group by model
python3 fleet_cost.py --json          # machine-readable
```

No dependencies beyond the Python standard library.

## Pricing

List-price estimates from the published per-MTok rates, not a billed invoice.
The cache is priced at its real multipliers, which is the whole point: cache
reads at 0.1x the base input rate, 5-minute cache writes at 1.25x, 1-hour cache
writes at 2x. Update the `PRICES` table if rates change.

## Honest scope

This sees **Claude Code** usage only. Agents that call the API directly, rather
than through Claude Code, bill separately and do not write to these logs, so
they are not counted. It is the coding-agent bill, not the whole bill.

## What it showed us

Over 30 days: cache reads were 99% of every token (2.0 billion of them), costing
about a tenth of what they would at full input price. The cache quietly saved
roughly $9,000 in a month. And the cheapest model, Haiku, was still a third of
the spend, because subagent fan-out reads a large cached context per worker.
