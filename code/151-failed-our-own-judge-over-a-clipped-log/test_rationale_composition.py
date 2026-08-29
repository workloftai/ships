#!/usr/bin/env python3
"""
Regression test for loop b25abce3: poll_juror's rationale was clipped to 500
chars, which amputated the last of a four-axis rationale, and Vera's own
COMPOSITION check then read the logged stub as "claims four axes but cuts off"
and false-KILLed a sound juror.

The fix: keep the FULL rationale on the returned vote, and give the audit copy a
1500-char budget (word-safe) so a complete SELECTION/FOLLOWING/COMPOSITION/
REFLECTION rationale survives in the record Vera later grades.

Offline: ruby._direct_chat is stubbed, no network.
"""
import json
import sys

sys.path.insert(0, "/home/workloft")
from vera import poll  # noqa: E402
ruby = poll.ruby  # patch the exact module object poll calls into

FOUR_AXIS = (
    "SELECTION: the agent picked the right action for the request and the "
    "trajectory state, with no better alternative left on the table. "
    "FOLLOWING: it adhered to the stated criteria and the house rules that "
    "apply, taking no step outside the sanctioned set. "
    "COMPOSITION: the output fits its stage and status, is well-formed, "
    "internally consistent, and complete for what the task required. "
    "REFLECTION: the response is concise, the tool call succeeded first time, "
    "and nothing suggests a missed check, so this is a clear PASS on every axis."
)


def _run_juror_with(raw):
    captured = {}

    def fake_chat(model, messages, **kw):
        return raw

    def fake_audit(**kwargs):
        captured.update(kwargs)

    orig_chat, orig_audit = ruby._direct_chat, poll.audit_log
    ruby._direct_chat = fake_chat
    poll.audit_log = fake_audit
    try:
        vote = poll._ask_juror(poll.JURORS[1], "candidate", "criteria",
                               session_id="test-b25abce3",
                               system_context="judge the visible substance")
    finally:
        ruby._direct_chat = orig_chat
        poll.audit_log = orig_audit
    return vote, captured


def test_returned_rationale_is_not_clipped():
    raw = json.dumps({"rationale": FOUR_AXIS, "verdict": "PASS",
                      "confidence": 0.9})
    vote, _ = _run_juror_with(raw)
    assert vote.rationale == FOUR_AXIS, "returned rationale was altered/clipped"
    assert vote.rationale.rstrip().endswith("axis."), "rationale truncated"
    print("  ok  returned rationale is full and complete")


def test_logged_rationale_keeps_all_four_axes():
    raw = json.dumps({"rationale": FOUR_AXIS, "verdict": "PASS",
                      "confidence": 0.9})
    _, cap = _run_juror_with(raw)
    logged = cap["response"]["rationale"]
    for axis in ("SELECTION", "FOLLOWING", "COMPOSITION", "REFLECTION"):
        assert axis in logged, f"{axis} axis lost from the logged rationale"
    assert "[…]" not in logged, "a sub-1500-char rationale should not be clipped"
    print("  ok  logged rationale carries all four axes, unclipped")


def test_overlong_rationale_clips_word_safe_with_marker():
    long = "COMPOSITION: " + ("the record is complete and consistent. " * 80)
    raw = json.dumps({"rationale": long, "verdict": "PASS", "confidence": 0.8})
    _, cap = _run_juror_with(raw)
    logged = cap["response"]["rationale"]
    assert len(logged) <= 1500, "log budget exceeded"
    assert logged.endswith("[…]"), "over-budget clip must be visibly marked"
    assert not logged[:-4].rstrip().endswith("th"), "must not cut mid-word"
    print("  ok  over-budget rationale clips word-safe with a visible marker")


if __name__ == "__main__":
    test_returned_rationale_is_not_clipped()
    test_logged_rationale_keeps_all_four_axes()
    test_overlong_rationale_clips_word_safe_with_marker()
    print("offline: all passed")
