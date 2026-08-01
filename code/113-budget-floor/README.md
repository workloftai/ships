# budget-floor: a hard floor under runaway agent loops

An autonomous agent on a retry loop can spend without bound. It never errors, it
just keeps calling the model. Amazon ran an internal Claude deployment 860% over
budget for five months on a misconfigured retry loop before anyone noticed, a
bill reported around $1.8M. The failure is not the model, it is the missing floor.

`fleet_guard.py` is that floor. Zero dependencies, stdlib only.

## Why not just count in memory

Most in-process guards keep the count in a variable, so a loop that restarts the
process each iteration (a cron every minute, a supervisor respawning on crash)
resets its own counter and the cap never bites. `fleet_guard` persists the count
to disk and measures spend over a rolling time window, so the floor holds across
restarts and decays on its own.

## Use

```python
from fleet_guard import BudgetGuard, BudgetExceeded

guard = BudgetGuard(
    "nightly-summariser",
    max_cost_usd=5.0,     # no more than $5 ...
    max_iterations=500,   # ... or 500 calls ...
    window_s=3600,        # ... per rolling hour
)
while work_remaining():
    guard.tick(tokens=resp_tokens, cost_usd=resp_cost)  # raises BudgetExceeded when a cap is hit
    do_one_iteration()
```

`BudgetExceeded` is not a subclass of any provider error, so it propagates out of
a loop that only catches transport errors and actually halts it.

## Kill-switch

One file halts every guard sharing a ledger dir, no deploy:

```bash
python3 fleet_guard.py stop     # drop the kill-switch
python3 fleet_guard.py resume   # clear it
python3 fleet_guard.py status nightly-summariser
```

## Demo

```bash
python3 demo.py
```

Reproduces a runaway loop (100k calls, $200, still going), then adds one line,
`guard.tick(...)`, and watches it halt at a $1 floor, then shows a fresh process
on the same ledger is already over cap.

## Caps

`max_tokens`, `max_cost_usd`, `max_iterations`, any combination (at least one).
`window_s` makes them per-window budgets; omit it for a lifetime cap.
