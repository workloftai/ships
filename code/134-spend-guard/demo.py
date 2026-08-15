#!/usr/bin/env python3
"""demo.py — watch the guardrail stay silent on a normal day, then trip.

No network, no store, no keys. Two synthetic days of a small agent fleet's
cost log run through the same `analyse` the cron uses.

    python3 demo.py
"""
from datetime import datetime, timedelta, timezone

from spend_guard import Config, analyse

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def row(days_ago, agent, cost, *, action="chat", tier="cheap", category="classify"):
    # subtract a minute so each row lands squarely inside its own 24h window
    return {
        "created_at": (NOW - days_ago * DAY - timedelta(minutes=1)).isoformat(),
        "agent": agent, "action": action, "cost_usd": cost,
        "arguments": {"tier": tier, "category": category},
    }


def normal_baseline():
    """Seven prior days of a well-behaved fleet: cheap routing, a little spend,
    a steady trickle of harmless failovers (a classifier cold-loading)."""
    rows = []
    for d in range(1, 8):
        rows += [row(d, "bob", 0.004), row(d, "walt", 0.002), row(d, "ruby", 0.006)]
        rows += [row(d, "walt", 0.0, action="chat_failover") for _ in range(35)]
    return rows


def show(title, rows):
    v = analyse(rows, NOW, Config())
    t = v["today"]
    print(f"\n=== {title} ===")
    print(f"  today: fleet ${t['fleet']:.3f} | premium ${t['premium']:.3f} | "
          f"failovers {t['failover']}  (baseline median ${v['fleet_base']:.3f})")
    if v["findings"]:
        print("  TRIPPED:")
        for f in v["findings"]:
            print(f"    - {f}")
    else:
        print("  clean — silent, no alert sent.")


# Day 1: a normal day. Today looks like the baseline. Nothing fires.
show("A normal day", normal_baseline() + [
    row(0, "bob", 0.004), row(0, "walt", 0.002), row(0, "ruby", 0.006),
    *[row(0, "walt", 0.0, action="chat_failover") for _ in range(38)],
])

# Day 2: bob's loop runs away on the premium tier, and a provider goes down so
# the router burns retries. Two rules should trip.
show("The day it goes wrong", normal_baseline() + [
    row(0, "bob", 4.20, tier="premium", category="reason_hard"),
    row(0, "bob", 0.35, tier="premium", category="classify"),  # premium on cheap work
    row(0, "ruby", 0.006),
    *[row(0, "walt", 0.0, action="chat_failover") for _ in range(260)],
])

print("\nSilent on the first, one alert on the second. That is the whole job.")
