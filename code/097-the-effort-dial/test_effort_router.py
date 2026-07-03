"""Tests for effort_router. Run: python3 test_effort_router.py"""
from effort_router import apply_effort, effort_for, supports_effort


def test_tier_mapping():
    assert effort_for("cheap", "claude-fable-5") == "low"
    assert effort_for("balanced", "claude-sonnet-4-6") == "medium"
    # premium keeps the API default — nothing is sent
    assert effort_for("premium", "claude-fable-5") is None
    # unknown tiers behave like premium
    assert effort_for("wat", "claude-fable-5") is None


def test_model_gate():
    # Haiku 4.5 rejects the parameter — must never be sent
    assert not supports_effort("claude-haiku-4-5-20251001")
    assert effort_for("cheap", "claude-haiku-4-5-20251001") is None
    assert supports_effort("claude-opus-4-8")
    assert supports_effort("claude-sonnet-5")
    assert not supports_effort("claude-sonnet-4-5")


def test_apply_effort():
    body = {"model": "claude-opus-4-8", "max_tokens": 64}
    apply_effort(body, "balanced")
    assert body["output_config"] == {"effort": "medium"}

    # premium leaves the body untouched (byte-stable for prompt caching)
    body2 = {"model": "claude-opus-4-8", "max_tokens": 64}
    apply_effort(body2, "premium")
    assert "output_config" not in body2

    # gated model leaves the body untouched even on cheap
    body3 = {"model": "claude-haiku-4-5-20251001", "max_tokens": 64}
    apply_effort(body3, "cheap")
    assert "output_config" not in body3

    # existing output_config keys survive
    body4 = {"model": "claude-fable-5", "output_config": {"format": {"type": "json_schema", "schema": {}}}}
    apply_effort(body4, "cheap")
    assert body4["output_config"]["effort"] == "low"
    assert "format" in body4["output_config"]


if __name__ == "__main__":
    test_tier_mapping()
    test_model_gate()
    test_apply_effort()
    print("all tests passed")
