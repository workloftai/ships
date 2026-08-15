#!/usr/bin/env python3
"""Tests for the spend_guard rule engine. Pure, offline, no store.

    python3 -m pytest test_spend_guard.py -q
    # or just: python3 test_spend_guard.py
"""
from datetime import datetime, timedelta, timezone

from spend_guard import Config, analyse, _window_index

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def row(days_ago, agent="bob", cost=0.0, *, action="chat", tier="cheap",
        category="classify"):
    # subtract a minute so each row lands squarely inside its own 24h window
    return {
        "created_at": (NOW - days_ago * DAY - timedelta(minutes=1)).isoformat(),
        "agent": agent, "action": action, "cost_usd": cost,
        "arguments": {"tier": tier, "category": category},
    }


def _baseline(per_day_cost=0.01, failovers=0):
    rows = []
    for d in range(1, 8):
        rows.append(row(d, "bob", per_day_cost))
        rows += [row(d, "bob", 0.0, action="chat_failover") for _ in range(failovers)]
    return rows


# ── windowing ────────────────────────────────────────────────────────────────

def test_window_index_buckets_by_24h():
    assert _window_index(NOW.isoformat(), NOW, 7) == 0
    assert _window_index((NOW - DAY - timedelta(hours=1)).isoformat(), NOW, 7) == 1
    assert _window_index((NOW - 8 * DAY).isoformat(), NOW, 7) is None  # older than baseline

def test_window_ignores_unparseable_and_future():
    assert _window_index("not-a-date", NOW, 7) is None
    assert _window_index((NOW + timedelta(hours=2)).isoformat(), NOW, 7) == 0


# ── rule 1: fleet spike ──────────────────────────────────────────────────────

def test_quiet_day_is_silent():
    rows = _baseline(0.01) + [row(0, "bob", 0.01)]
    assert analyse(rows, NOW, Config())["findings"] == []

def test_fleet_spike_trips():
    # baseline ~0.01/day, today 5.00 -> way over max(floor 1.00, 0.01*3)
    rows = _baseline(0.01) + [row(0, "bob", 5.00)]
    v = analyse(rows, NOW, Config())
    assert any("Fleet spend" in f for f in v["findings"])

def test_floor_suppresses_relative_only_noise():
    # today is 3x the tiny baseline but still under the absolute floor -> silent
    rows = _baseline(0.02) + [row(0, "bob", 0.10)]
    v = analyse(rows, NOW, Config())
    assert not any("Fleet spend" in f for f in v["findings"])


# ── rule 2: per-agent spike ──────────────────────────────────────────────────

def test_agent_spike_names_the_agent():
    rows = _baseline(0.01)
    rows += [row(0, "bob", 0.01), row(0, "maggie", 2.00)]  # maggie is the outlier
    v = analyse(rows, NOW, Config())
    assert any("maggie" in f and "spend" in f for f in v["findings"])


# ── rule 3: premium tier ─────────────────────────────────────────────────────

def test_premium_tier_surfaced_and_cheap_flagged():
    rows = _baseline(0.01) + [
        row(0, "bob", 0.60, tier="premium", category="classify"),  # cheap-eligible
    ]
    v = analyse(rows, NOW, Config())
    prem = [f for f in v["findings"] if "Premium tier" in f]
    assert prem and "cheap-eligible" in prem[0]

def test_premium_under_floor_silent():
    rows = _baseline(0.01) + [row(0, "bob", 0.05, tier="premium", category="reason_hard")]
    v = analyse(rows, NOW, Config())
    assert not any("Premium tier" in f for f in v["findings"])


# ── rule 4: failover storm ───────────────────────────────────────────────────

def test_failover_storm_trips_over_baseline():
    rows = _baseline(0.01, failovers=35)  # steady ~35/day baseline
    rows += [row(0, "bob", 0.01)] + [row(0, "walt", 0.0, action="chat_failover")
                                     for _ in range(200)]
    v = analyse(rows, NOW, Config())
    assert any("Failover storm" in f for f in v["findings"])

def test_normal_failover_trickle_silent():
    rows = _baseline(0.01, failovers=35)
    rows += [row(0, "bob", 0.01)] + [row(0, "walt", 0.0, action="chat_failover")
                                     for _ in range(38)]
    v = analyse(rows, NOW, Config())
    assert not any("Failover storm" in f for f in v["findings"])


# ── robustness ───────────────────────────────────────────────────────────────

def test_missing_and_null_fields_do_not_crash():
    rows = [
        {"created_at": NOW.isoformat()},                       # no cost/agent/args
        {"created_at": NOW.isoformat(), "cost_usd": None, "arguments": None},
        {"created_at": NOW.isoformat(), "arguments": {"tier": "premium"}},  # no category
    ]
    v = analyse(rows, NOW, Config())
    assert v["n_rows"] == 3  # ran clean, counted every row

def test_empty_input_is_silent():
    v = analyse([], NOW, Config())
    assert v["findings"] == [] and v["n_rows"] == 0


if __name__ == "__main__":
    import sys
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}  {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
