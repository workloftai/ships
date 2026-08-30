# cost_guardrail — refuse the expensive model switch before it bills a token

You find out you blew the budget on the invoice, after the tokens are spent. By
then the money is gone. This moves the decision to the moment of the switch: the
instant a session reaches for a premium model, a hook checks whether the day's
budget is gone and, if it is, blocks the switch before the model is ever called.

Claude Code v2.1.251 added the `PreModelSwitch` hook event. It fires *before* the
session changes model and, unusually, it can block (exit code 2). That is the
lever cost control never had. Every other cost tool is a rear-view mirror. This
is a hand on the wheel.

```bash
python3 test_cost_guardrail.py   # 14 passed, 0 failed
```

## What it does

- Decides by **tier**, not by exact model id, so a new model name never needs a
  code change: any name containing `haiku` < `sonnet`/`fable` < `opus`.
- A **downgrade or lateral move always passes**. Only an *upgrade into the
  premium tier* is gated.
- A premium upgrade is **denied (exit 2)** if today's spend has hit the daily
  budget, allowed otherwise, with the cost multiplier noted (`~15x the per-token
  cost of claude-haiku-4-5`).
- Every decision is appended to a JSONL log, so the guard is also the feedback
  loop: you can see exactly how often the fleet tried to reach for Opus and got
  told no.

Real block:

```json
{"hookSpecificOutput": {"hookEventName": "PreModelSwitch",
  "permissionDecision": "deny",
  "permissionDecisionReason": "Daily budget $5.00 exhausted ($6.20 spent). Switch claude-haiku-4-5 -> claude-opus-4-8 blocked."}}
# exit code 2 -> the switch does not happen
```

## Wire it in

`~/.claude/settings.json`:

```json
{ "hooks": { "PreModelSwitch": [
    { "matcher": ".*opus.*",
      "hooks": [ { "type": "command",
                   "command": "python3 /path/to/cost_guardrail.py" } ] } ] } }
```

The matcher scopes the guard to switches that reach the premium tier, which is
the only case it acts on. Edit `cost_policy.json` for your tiers, prices, daily
budget, and any sessions that bypass the gate.

## Feed it your spend

The guard reads today's spend from a JSONL ledger you own, one line per billed
action: `{"ts": "<iso8601>", "cost": 0.012}`. Point `ledger_path` at it. Feed it
from wherever your spend already lives: the v2.1.251 `rate_limits.spend_limit`
status-line field, an audit log, or a Postgres query dumped to a file. The guard
does not care where the number comes from, only that it is today's total.

## The one rule: fail open

A cost guard that bricks the fleet on its own bug is worse than the overspend it
prevents. Unparseable input, a missing policy, an unknown model, any exception:
the guard allows the switch and exits 0. It only ever says no when it is certain.
That is why the test harness asserts garbage stdin still exits 0.

## Honest limits

- Requires Claude Code **v2.1.251+** for the `PreModelSwitch` event. On older
  builds the hook simply never fires, so nothing breaks, nothing is enforced.
- It gates *model switches*, not raw token spend inside one model. A session
  already on Opus is not stopped mid-flight; it stops the *next* upgrade.
- The budget check is only as good as the ledger you feed it. A stale or empty
  ledger reads as `$0.00 spent`, which fails open by design.
- Prices in `cost_policy.json` are public list prices as a rough tier ordering.
  Set your own gateway/contract rates.

MIT. Steal what you want.
