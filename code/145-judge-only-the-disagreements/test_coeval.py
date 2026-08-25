"""Deterministic proof of coeval's selection rule and cost arithmetic.

No models, no network, no third-party deps. Run:  python3 test_coeval.py
"""
from __future__ import annotations

from dataclasses import dataclass

from coeval import (frontier_weight, select_for_panel, coeval_compare)


@dataclass
class Scn:
    scenario_id: str


# --- frontier_weight ---------------------------------------------------------

def test_disagreement_is_max_weight():
    assert frontier_weight("PASS", 0.99, "KILL", 0.99) == 1.0
    assert frontier_weight("KILL", 0.60, "PASS", 0.55) == 1.0

def test_confident_tie_is_low_weight():
    assert frontier_weight("PASS", 0.95, "PASS", 0.95) == 0.05
    assert frontier_weight("PASS", 0.60, "PASS", 0.70) == 0.40

def test_error_screen_forces_escalation():
    assert frontier_weight("ERROR", 0.0, "PASS", 0.9) == 1.0


# --- select_for_panel --------------------------------------------------------

def test_disagreements_always_panelled_even_at_zero_budget():
    weights = [1.0, 0.05, 1.0, 0.05, 1.0]
    chosen = select_for_panel(weights, escalate_conf_floor=0.75, panel_budget_frac=0.0)
    assert chosen == [True, False, True, False, True]

def test_floor_escalates_shaky_ties():
    weights = [0.05, 0.30, 0.10, 0.40]
    chosen = select_for_panel(weights, escalate_conf_floor=0.75, panel_budget_frac=1.0)
    assert chosen == [False, True, False, True]

def test_budget_cap_keeps_highest_weight_ties():
    weights = [1.0, 0.50, 0.40, 0.30, 1.0]
    chosen = select_for_panel(weights, escalate_conf_floor=0.9, panel_budget_frac=0.6)
    assert chosen[0] and chosen[4]                        # disagreements always in
    assert chosen[1] and not chosen[2] and not chosen[3]  # only the top tie fits


# --- end to end: net delta preserved, cost correct --------------------------

def test_coeval_preserves_net_delta_and_counts_cost():
    scenarios = [Scn(f"s{i}") for i in range(4)]
    # ground truth we want the panel to reflect:
    #   s0 KILL->PASS (fixed)      disagree -> panelled
    #   s1 PASS->PASS (stable)     agree hi-conf -> screen only
    #   s2 PASS->KILL (regressed)  disagree -> panelled
    #   s3 KILL->KILL (stable)     agree hi-conf -> screen only
    table = {
        ("before", "s0"): ("KILL", 0.9), ("after", "s0"): ("PASS", 0.9),
        ("before", "s1"): ("PASS", 0.95), ("after", "s1"): ("PASS", 0.95),
        ("before", "s2"): ("PASS", 0.9), ("after", "s2"): ("KILL", 0.9),
        ("before", "s3"): ("KILL", 0.92), ("after", "s3"): ("KILL", 0.92),
    }
    def screen(candidate, criteria, label):
        side, sid = label.split(":")
        v, c = table[(side, sid)]
        return v, c, 0.001
    def panel(candidate, criteria, label):
        side, sid = label.split(":")
        v, c = table[(side, sid)]
        return v, c, 0.009

    res = coeval_compare(
        scenarios,
        respond_before=lambda s: "b", respond_after=lambda s: "a",
        criteria_for=lambda s: "RUBRIC",
        screen_fn=screen, panel_fn=panel,
        escalate_conf_floor=0.75)

    assert res.fixed == 1 and res.regressed == 1 and res.net_delta == 0
    assert res.stable_pass == 1 and res.stable_kill == 1
    assert res.n_panelled == 2
    assert abs(res.panel_cost_usd - 4 * 0.009) < 1e-9    # 2 scenarios x 2 sides
    assert abs(res.screen_cost_usd - 8 * 0.001) < 1e-9   # 4 scenarios x 2 sides
    assert abs(res.full_panel_cost_estimate_usd - 8 * 0.009) < 1e-9
    assert 0.35 < res.savings_frac < 0.45


def test_all_agree_spends_no_panel():
    scenarios = [Scn(f"s{i}") for i in range(3)]
    def screen(candidate, criteria, label):
        return "PASS", 0.97, 0.001
    def panel(candidate, criteria, label):
        raise AssertionError("panel must not fire when nothing is on the frontier")
    res = coeval_compare(
        scenarios,
        respond_before=lambda s: "ok", respond_after=lambda s: "ok",
        criteria_for=lambda s: "R",
        screen_fn=screen, panel_fn=panel, escalate_conf_floor=0.75)
    assert res.n_panelled == 0 and res.panel_cost_usd == 0.0
    assert res.stable_pass == 3
    assert res.full_panel_cost_estimate_usd == 0.0


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
