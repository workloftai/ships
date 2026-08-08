"""Tests for the three-layer eval: precheck (L1), golden/kappa_gate (L3), and the
layers orchestrator (L1->L2). No network — the panel and scorer are stubbed.

Run:  python3 test_layers.py
"""
from __future__ import annotations

from precheck import precheck
from golden import GoldenRow, kappa_gate, load_golden, DEFAULT_SET
from layers import three_layer_evaluate


# --- Layer 1 ---------------------------------------------------------------

def test_precheck_empty_kills():
    r = precheck("", "write a summary")
    assert r.killed and r.hit.check == "empty_output"

def test_precheck_emptyish_placeholder_kills():
    assert precheck("null", "return a value").killed
    assert precheck("  N/A ", "return a value").killed

def test_precheck_empty_abstains_when_criteria_allows():
    assert not precheck("", "return the rows; empty is acceptable when none match").killed

def test_precheck_unmarked_failure_kills():
    r = precheck('{"success": false, "result": null}', "complete the action and return a result")
    assert r.killed and r.hit.check == "unmarked_failure"

def test_precheck_unmarked_failure_via_meta():
    r = precheck("some output text", "do the thing", meta={"success": False})
    assert r.killed and r.hit.check == "unmarked_failure"

def test_precheck_expected_failure_abstains():
    r = precheck('{"success": false, "note": "no rows, the expected empty case"}',
                 "complete the action; an empty result is acceptable")
    assert not r.killed

def test_precheck_success_true_abstains():
    assert not precheck('{"success": true, "result": 42}', "return a result").killed

def test_precheck_traceback_kills():
    r = precheck("Traceback (most recent call last):\n  KeyError: 'x'", "route it")
    assert r.killed and r.hit.check == "error_leak"

def test_precheck_error_token_ok_when_criteria_is_about_errors():
    assert not precheck("A ValueError: is raised when the input is not a number.",
                        "Explain when a ValueError is raised.").killed

def test_precheck_schema_violation_kills():
    r = precheck("here you go: name Jane", "return the fields as strict JSON")
    assert r.killed and r.hit.check == "schema_violation"

def test_precheck_valid_json_abstains():
    assert not precheck('{"name": "Jane"}', "return the fields as strict JSON").killed

def test_precheck_json_fence_tolerated():
    assert not precheck('```json\n{"a": 1}\n```', "return strict JSON").killed

def test_precheck_never_returns_pass():
    assert precheck("A perfectly good, substantive answer.", "answer well").verdict == "ABSTAIN"


# --- Layer 3 ---------------------------------------------------------------

def _l1_scorer(candidate, criteria):
    return "KILL" if precheck(candidate, criteria).killed else "PASS"

def test_seed_golden_loads():
    rows = load_golden(DEFAULT_SET)
    assert len(rows) >= 8 and all(r.human in ("PASS", "KILL") for r in rows)

def test_kappa_gate_perfect_agreement_high_kappa():
    res = kappa_gate(load_golden(DEFAULT_SET), scorer=_l1_scorer, min_rows=1)
    assert res.kappa == 1.0 and res.certified and not res.disagreements

def test_kappa_gate_withholds_certification_below_min_rows():
    res = kappa_gate([GoldenRow(candidate="", criteria="x", human="KILL")],
                     scorer=_l1_scorer, min_rows=30)
    assert not res.certified and "not a stable estimate" in res.warning

def test_kappa_gate_flags_disagreements():
    rows = [GoldenRow(candidate="good", criteria="c", human="PASS"),
            GoldenRow(candidate="also good", criteria="c", human="PASS")]
    res = kappa_gate(rows, scorer=lambda c, cr: "KILL", min_rows=1)
    assert len(res.disagreements) == 2 and not res.certified


# --- L1 -> L2 --------------------------------------------------------------

def test_layers_shortcircuit_on_precheck_kill():
    def panel(candidate, criteria, **kw):
        raise AssertionError("panel must not run after a Layer-1 kill")
    res = three_layer_evaluate('{"success": false}', "do the thing", panel=panel)
    assert res.verdict == "KILL" and res.layer == "precheck" and res.cost_usd == 0.0

def test_layers_falls_through_to_panel():
    class StubPanel:
        verdict = "PASS"; confidence = 0.9; total_cost_usd = 0.002; kill_shots = []
    res = three_layer_evaluate("a substantive answer", "answer well",
                               panel=lambda c, cr, **kw: StubPanel())
    assert res.layer == "panel" and res.verdict == "PASS"
    assert res.confidence == 0.9 and res.cost_usd == 0.002


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
