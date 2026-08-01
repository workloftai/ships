#!/usr/bin/env python3
"""
demo.py - reproduce a runaway agent loop, then put a floor under it.

No network, no keys, fully deterministic. It fakes a "summarise, retry on a
(never-arriving) success" loop, the shape of the Amazon incident: every call
costs money, the exit condition never fires, so without a floor it bills forever.

Run:  python3 demo.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fleet_guard import BudgetGuard, BudgetExceeded

# A fake model call: fixed token/cost per iteration, and "success" never comes.
COST_PER_CALL = 0.002   # $ per call, a cheap model
TOKENS_PER_CALL = 1500


def runaway_without_guard(max_show: int = 100_000):
    """What the misconfigured loop does: spend until someone notices."""
    calls = 0
    spend = 0.0
    while True:                       # the exit condition that never fires
        calls += 1
        spend += COST_PER_CALL
        if calls >= max_show:         # we stop the DEMO here; production had no stop
            return calls, spend


def guarded_loop(ledger_dir: str):
    """Same loop, one line added: guard.tick() before each unit of work."""
    guard = BudgetGuard(
        "demo-summariser",
        max_cost_usd=1.00,            # hard floor: $1
        max_iterations=2000,          # or 2000 calls, whichever first
        ledger_dir=ledger_dir,
    )
    guard.reset()                     # clean ledger for a repeatable demo
    calls = 0
    spend = 0.0
    try:
        while True:
            guard.tick(tokens=TOKENS_PER_CALL, cost_usd=COST_PER_CALL)
            calls += 1
            spend += COST_PER_CALL
    except BudgetExceeded as e:
        return calls, spend, e


def main() -> None:
    print("=" * 66)
    print("1) Runaway loop, NO guard (demo capped at 100k calls to stay finite)")
    calls, spend = runaway_without_guard()
    print(f"   ran {calls:,} calls, spent ${spend:,.2f} and still going.")
    print(f"   at Amazon's five-month duration this is how $1.8M happens.")
    print()

    print("2) Same loop, ONE line added: guard.tick(...)")
    with tempfile.TemporaryDirectory() as d:
        calls, spend, exc = guarded_loop(d)
        print(f"   halted after {calls:,} calls, ${spend:.2f} spent.")
        print(f"   reason: {exc.reason}")
        print(f"   final ledger: {exc.stats}")

        # Restart-safety: a fresh process pointed at the same ledger stays halted.
        print()
        print("3) Restart safety: a new guard on the SAME ledger is already over cap")
        reborn = BudgetGuard("demo-summariser", max_cost_usd=1.00,
                             max_iterations=2000, ledger_dir=d)
        try:
            reborn.check()
            print("   ERROR: guard did not hold across restart")
        except BudgetExceeded as e:
            print(f"   blocked on construction+check: {e.reason}")
    print("=" * 66)


if __name__ == "__main__":
    main()
