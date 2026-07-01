"""Tests for temporal_grounding. Dependency-free, run with: python3 test_temporal_grounding.py"""
import os

from temporal_grounding import anchor, ground, today_iso


def test_today_precedence():
    assert today_iso("2026-07-01") == "2026-07-01"          # explicit arg wins
    os.environ["JUDGE_TODAY"] = "2025-01-15"
    try:
        assert today_iso() == "2025-01-15"                  # env override
        assert today_iso("2026-07-01") == "2026-07-01"      # arg beats env
    finally:
        del os.environ["JUDGE_TODAY"]
    fb = today_iso()                                        # falls back to clock
    assert len(fb) == 10 and fb[4] == "-" and fb[7] == "-"


def test_anchor_states_date_and_bans_reason():
    a = anchor("2026-07-01")
    assert "2026-07-01" in a
    assert "TEMPORAL GROUNDING" in a
    assert "postdates" in a
    assert "never a valid reason to reject" in a


def test_ground_prepends_and_keeps_original():
    base = "You are a strict reviewer."
    out = ground(base, today="2026-07-01")
    assert out.endswith(base)                               # original preserved
    assert out.startswith("TEMPORAL GROUNDING")            # anchor on top
    assert "2026-07-01" in out


def test_inert_shape_on_datefree_prompt():
    # grounding is always the same fixed preamble plus the prompt; it never
    # rewrites the candidate, so it cannot corrupt a date-free judge prompt.
    base = "Grade the answer 1-5."
    assert ground(base, today="2026-07-01").count(base) == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("all passed")
