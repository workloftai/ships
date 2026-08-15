# spend-guard — a tripwire on an agent fleet's model spend

Routing to the cheapest capable model and logging every call's cost gives you
the *data* to catch a runaway. It doesn't give you anything that **watches** it.
So the runaway loop, the credit drain, the day one agent starts leaning on the
premium tier, all show up the same way: on the bill.

This is the missing watcher. It reads your per-call cost log, compares the last
24h against a trailing baseline, and speaks only when a rule trips. It alerts, it
does not enforce. Hard-capping a call mid-flight is a separate, riskier job; this
is the eyes that come first.

## The rules

Trailing 24h vs the median of the prior N days. Every rule pairs a relative
multiple with an absolute floor, so a quiet fleet doesn't false-alarm on noise
(3x of near-zero is still near-zero).

1. **Fleet spend spike** — total spend today over `max(floor, median * mult)`.
2. **Agent spend spike** — same, per agent, so the alert names who.
3. **Premium-tier spend** — the expensive escalation rung, surfaced when a day
   leans on it; premium spend on cheap-eligible categories gets an extra flag.
4. **Failover storm** — retries today well over baseline: a provider is down or
   blocked and the router is burning attempts.

## Run it

```bash
python3 demo.py                          # two synthetic days: one silent, one trips
python3 test_spend_guard.py              # 12 tests, no network
```

The engine is pure. `analyse(rows, now, cfg)` takes a list of log rows and
returns the verdict, which is why the demo and tests need no store and no keys.

```python
from spend_guard import analyse, Config
v = analyse(rows, cfg=Config(spike_mult=3.0, fleet_floor=1.00))
for finding in v["findings"]:
    print(finding)
```

Each row is a dict:

```python
{"created_at": "2026-08-15T12:00:00Z", "agent": "bob", "action": "chat",
 "cost_usd": 0.004, "arguments": {"tier": "cheap", "category": "classify"}}
```

## Wire it to your world

Two functions are the seams, both reading config from the environment so no
secret lands in source:

- `fetch_rows(now, cfg)` — the reference reads a Supabase/PostgREST table
  (`AUDIT_DB_URL`, `AUDIT_DB_KEY`, `AUDIT_DB_TABLE`), paging past the 1000-row
  response cap so a spend total never silently undercounts. Swap it for a
  warehouse query or a JSONL read.
- `alert(text)` — posts to Telegram if `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
  are set, else prints. Swap for Slack, PagerDuty, email.

Then run it on a schedule (daily is plenty). The discipline that matters:
**silent when clean, one message when not.** An alarm that fires every day is one
nobody reads.

## What's still off

It alerts, it does not enforce. It reads whatever your log records, so an agent
that calls a model without logging the cost is invisible to it. Relevance of
"cheap-eligible" is a category allow-list you set, not something it infers. And
the baseline is a plain median, not seasonal, so a genuine step-change in fleet
size needs the floors nudged. It is a smoke detector, not a sprinkler. Its whole
value is the day something breaks and you hear about it in minutes, not on the
invoice.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
