"""effort_router — map a routing tier onto Anthropic's effort parameter.

The idea from the ship "Every agent in the fleet was set to maximum effort"
(workloft.ai/ships/the-effort-dial-2026-07-03.html), stripped to a
dependency-free function you can drop into any router.

If your system already routes model choice by a cost-quality tier
(premium / balanced / cheap), the tier should set effort too:

    premium  -> high  (the API default; we don't send it)
    balanced -> medium
    cheap    -> low

Two rules make this safe:

1. Only send `output_config.effort` to models that accept it. Haiku 4.5
   and pre-4.6 Sonnets return a 400 on the parameter.
2. Never send "high" explicitly — it's the default, and omitting it keeps
   request bodies byte-stable for prompt caching.
"""
from __future__ import annotations

# Model-id prefixes that accept output_config.effort (GA, no beta header).
# Verified against the Anthropic model catalogue, 2026-07-03.
EFFORT_CAPABLE_PREFIXES = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-4-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-sonnet-5",
)

EFFORT_BY_TIER = {
    "premium": None,      # keep the API default (high)
    "balanced": "medium",
    "cheap": "low",
}


def supports_effort(model_id: str) -> bool:
    """True if the model accepts output_config.effort."""
    return model_id.startswith(EFFORT_CAPABLE_PREFIXES)


def effort_for(tier: str, model_id: str) -> str | None:
    """The effort level to send for this (tier, model) pair, or None to omit.

    Unknown tiers behave like premium: send nothing, run at the default.
    """
    level = EFFORT_BY_TIER.get(tier)
    if level is None or not supports_effort(model_id):
        return None
    return level


def apply_effort(body: dict, tier: str) -> dict:
    """Set output_config.effort on a Messages API request body, in place.

    `body` must already carry its "model". Returns the body for chaining.
    """
    level = effort_for(tier, body.get("model", ""))
    if level:
        body.setdefault("output_config", {})["effort"] = level
    return body
