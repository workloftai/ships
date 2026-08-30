#!/usr/bin/env python3
"""
Regression test for loop c39cc32d: the standing eval's tier-0 gate blanket-held
any response carrying a `text_preview` key as "truncated", so COMPLETE short
router outputs (a full classification JSON of a few hundred chars) were escalated
as truncated and then false-KILLed by the strong reviewer for fields that were
present inside the preview string. The distiller (Ship #162) traced ~91 ruby/chat
false-KILLs to this.

Fix: `_preview_complete` distinguishes a finished output from a genuine cut-off,
and `_tier0_gate` unwraps a complete preview to score the real content, holding
only genuinely truncated ones.

Offline: no network, no model calls.
"""
import sys

sys.path.insert(0, "/home/workloft")
from vera import standing  # noqa: E402
from vera.rubric_gen import Trajectory  # noqa: E402


def _mk(resp):
    return Trajectory(agent="ruby", action="chat", tool="gemini-2-5-flash",
                      arguments={"tier": "cheap", "max_tokens": 300},
                      response=resp, success=True, cost_usd=0.0001,
                      duration_ms=800, created_at="2026-08-29T00:00:00Z")


COMPLETE = ('{"score": 4, "axis": "agent infra", "hook": "a real hook here", '
            '"buildability": "yes", "effort_days": 3}')
FENCED = '```json\n{"score": 2, "axis": "x", "effort_days": null}\n```'
TRUNC = '{"score": 4, "axis": "other", "hook": "This blog post discusses the imp'


def test_preview_complete_detection():
    assert standing._preview_complete(COMPLETE) is True
    assert standing._preview_complete(FENCED) is True
    assert standing._preview_complete(TRUNC) is False
    assert standing._preview_complete("") is False
    print("  ok  _preview_complete separates finished JSON from a cut-off")


def test_complete_envelope_is_unwrapped_not_held():
    t = _mk({"model": "gemini-2-5-flash", "provider": "google",
             "text_preview": COMPLETE})
    ok, reason = standing._tier0_gate(t)
    assert ok is True, f"complete envelope was held: {reason}"
    assert isinstance(t.response, str) and '"score"' in t.response, \
        "response was not unwrapped to the real output"
    print("  ok  complete router envelope passes the gate and is unwrapped")


def test_truncated_envelope_still_held():
    t = _mk({"model": "x", "provider": "y", "text_preview": TRUNC})
    ok, reason = standing._tier0_gate(t)
    assert ok is False and "truncated" in reason
    print("  ok  a genuinely truncated preview is still held")


def test_non_envelope_response_unaffected():
    t = _mk({"verdict": "PASS", "rationale": "a complete rationale.",
             "confidence": 0.9})
    ok, _ = standing._tier0_gate(t)
    assert ok is True
    print("  ok  a non-envelope response (poll_juror shape) is unaffected")


if __name__ == "__main__":
    test_preview_complete_detection()
    test_complete_envelope_is_unwrapped_not_held()
    test_truncated_envelope_still_held()
    test_non_envelope_response_unaffected()
    print("offline: all passed")
