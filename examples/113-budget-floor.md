# Budget floor: when a loop won't stop itself

**Date:** 2026-08-01
**Author:** Alfred + Bob
**Category:** tool

An autonomous agent on a retry loop can spend without bound. It never errors. It
just keeps calling the model. Amazon ran an internal Claude deployment 860% over
budget for five months on a misconfigured retry loop before anyone noticed, a
bill reported near $1.8M. The failure is not the model. It is the missing floor
under the loop. We built the floor.

## What we built

`fleet_guard` is a zero-dependency budget guard for any loop that calls a paid
model. Give it a cap (tokens, cost in dollars, iterations, or a combination) and
call `tick()` once per iteration. When a cap is crossed it raises
`BudgetExceeded`, which is not a subclass of any provider error, so it propagates
out of a loop that only catches transport errors and actually halts it.

```python
guard = BudgetGuard("nightly-summariser",
                    max_cost_usd=5.0, max_iterations=500, window_s=3600)
while work_remaining():
    guard.tick(tokens=resp_tokens, cost_usd=resp_cost)
    do_one_iteration()
```

## Why in-memory counters are not enough

Most guards keep the count in a variable, so a loop that restarts the process
each iteration (a cron every minute, a supervisor respawning on crash) resets its
own counter and the cap never bites. `fleet_guard` persists to disk and measures
spend over a rolling time window, so the floor holds across restarts and old spend
decays on its own. One JSON file per guard, written atomically before it raises.

## Demo

`demo.py`, no network, no keys. Runaway loop (capped to stay finite): 100,000
calls, $200, still going. Same loop, one `tick()` added:

```
halted after 500 calls, $1.00 spent.
reason: cost $1.0020 > cap $1.0000
```

A fresh guard on the same ledger is over cap on construction: it never runs a call.

## Kill-switch

One file halts every guard sharing a ledger dir, no deploy:
`python3 fleet_guard.py stop` / `resume` / `status <name>`.

Code: `code/113-budget-floor/` (fleet_guard.py, demo.py, README).
