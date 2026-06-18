"""Tests for the governed self-improving loop. Run: python3 -m pytest -q (or python3 test_harness_gate.py)."""
from __future__ import annotations

from harness_gate import (
    ChangeLog, GovernedLoop, HarnessEdit, Proposer, ReviewGate, Verdict, score,
)


def _pass_if(predicate):
    return lambda h: predicate(h)


def test_gate_rejects_held_out_regression():
    # Edit looks great on dev but the gate's held-out set regresses.
    dev = [_pass_if(lambda h: h.get("x"))]            # x=True -> 1.0 on dev
    held = [_pass_if(lambda h: not h.get("x"))]       # x=True -> 0.0 on held-out
    gate = ReviewGate(held, floor=0.0)
    v = gate.review({"x": False}, HarnessEdit("set x", {"x": True}, 1.0))
    assert v.accepted is False
    assert v.held_out_before == 1.0 and v.held_out_after == 0.0


def test_gate_accepts_genuine_gain():
    held = [_pass_if(lambda h: h.get("retries", 1) >= 3)]
    gate = ReviewGate(held, floor=0.0)
    v = gate.review({"retries": 1}, HarnessEdit("retries", {"retries": 3}, 0.0))
    assert v.accepted is True
    assert v.held_out_after > v.held_out_before


def test_gate_ignores_proposer_claim():
    # A wildly optimistic claimed_delta must not buy acceptance.
    held = [_pass_if(lambda h: not h.get("x"))]
    gate = ReviewGate(held, floor=0.0)
    v = gate.review({"x": False}, HarnessEdit("set x", {"x": True}, 99.0))
    assert v.accepted is False


def test_loop_picks_honest_edit_over_overfit():
    dev = ([_pass_if(lambda h: h.get("cache"))] * 3) + [_pass_if(lambda h: h.get("retries", 1) >= 3)]
    held = ([_pass_if(lambda h: not h.get("cache"))] * 3) + [_pass_if(lambda h: h.get("retries", 1) >= 3)]
    cands = [HarnessEdit("cache", {"cache": True}, 0.0),
             HarnessEdit("retries", {"retries": 3}, 0.0)]
    loop = GovernedLoop({"retries": 1}, Proposer(dev, cands), ReviewGate(held, floor=0.0))
    loop.step()
    assert loop.harness.get("cache") is not True   # overfit edit refused
    assert loop.harness.get("retries") == 3        # honest edit landed


def test_log_is_tamper_evident():
    log = ChangeLog()
    log.append(harness_version=0,
               verdict=Verdict(HarnessEdit("e", {"a": 1}, 0.0), True, 0.0, 1.0, "ok"))
    log.append(harness_version=1,
               verdict=Verdict(HarnessEdit("f", {"b": 2}, 0.0), False, 1.0, 1.0, "no gain"))
    assert log.verify() is True
    log.entries[0].accepted = False      # forge a past record
    assert log.verify() is False         # chain detects it


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
