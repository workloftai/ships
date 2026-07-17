"""Tests for deepfix. Offline only: no network, no model calls.

    python3 -m pytest test_deepfix.py -q
    # or, no pytest:
    python3 test_deepfix.py
"""
from __future__ import annotations

import deepfix


def _trace():
    return deepfix.Trace(
        task="write a markdown plan; rule: never use `any`",
        steps=[
            {"id": 1, "thought": "outline the stages"},
            {"id": 2, "thought": "the no-any rule is absolute so i must enforce it in this markdown too"},
        ],
        answer="...",
    )


def test_edit_records_before_and_after():
    t = _trace()
    corr = deepfix.edit(t, step_id=2, corrected="markdown is exempt; just write the plan")
    assert corr.step_id == 2
    assert "absolute" in corr.before
    assert corr.after == "markdown is exempt; just write the plan"
    assert t.correction is not None


def test_edit_unknown_step_raises():
    t = _trace()
    try:
        deepfix.edit(t, step_id=99, corrected="x")
    except KeyError:
        return
    raise AssertionError("editing an unknown step should raise KeyError")


def test_distil_verbatim_without_llm():
    corr = deepfix.Correction(step_id=2, before="wrong", after="the full worked correction text")
    d = deepfix.distil(corr, use_llm=False)
    assert d.verbatim is True
    assert d.rule == "the full worked correction text"
    assert d.source_step == 2


def test_cost_verbatim_saves_nothing():
    corr = deepfix.Correction(step_id=2, before="wrong", after="same text repeated")
    d = deepfix.distil(corr, use_llm=False)
    c = deepfix.cost(corr, d, runs=10)
    assert c["saved_per_run"] == 0
    assert c["verbatim_directive"] is True


def test_cost_distilled_saves_tokens():
    # a long correction compressed into a short rule should save tokens
    corr = deepfix.Correction(
        step_id=2,
        before="wrong",
        after=("The no-any rule targets TypeScript source, not this markdown plan, so "
               "it does not apply here and I will not spend a pass enforcing it across "
               "every line of prose before writing the actual plan content."),
    )
    short = deepfix.Directive(rule="Scope the no-`any` rule to code files.", source_step=2, verbatim=False)
    c = deepfix.cost(corr, short, runs=100)
    assert c["saved_per_run"] > 0
    assert c["saved_pct"] > 0
    assert c["saved_over_runs"] == c["saved_per_run"] * 100


def test_apply_prepends_directives():
    d = deepfix.Directive(rule="Scope the no-any rule to code files.", source_step=2)
    out = deepfix.apply("do the thing", [d])
    assert "Standing directives" in out
    assert "Scope the no-any rule" in out
    assert out.strip().endswith("Task: do the thing")


def test_apply_no_directives_is_passthrough():
    assert deepfix.apply("just the task", []) == "just the task"


def test_count_tokens_returns_positive():
    n, exact = deepfix.count_tokens("hello world")
    assert n > 0
    assert isinstance(exact, bool)


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")


if __name__ == "__main__":
    _run_all()
