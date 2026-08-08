"""Three-layer evaluation — the Airbnb model.

    Layer 1  precheck   deterministic, no LLM     kills the obvious, spends nothing
    Layer 2  panel      your LLM judge            judges the rest
    Layer 3  kappa_gate golden set vs human       certifies the judge itself

Layers 1 and 2 run per candidate (`three_layer_evaluate`). Layer 3 is periodic:
it certifies whether the panel's verdicts can be trusted at all.

The panel is injectable. This standalone drop ships no LLM panel, so you must pass
`panel=...` (anything with the shape (candidate, criteria, **kw) -> result, where
result has `.verdict` and optionally `.confidence`/`.total_cost_usd`/`.kill_shots`,
or is a dict with those keys).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from precheck import precheck


@dataclass
class LayeredResult:
    verdict: str
    confidence: float
    layer: str                   # "precheck" | "panel"
    reason: str
    cost_usd: float = 0.0
    check: str | None = None
    panel_result: Any | None = None


PanelFn = Callable[..., Any]


def three_layer_evaluate(candidate: str, criteria: str = "", *,
                         meta: dict | None = None,
                         panel: PanelFn | None = None,
                         **panel_kwargs: Any) -> LayeredResult:
    """Run Layer 1 then, only if it abstains, Layer 2. A Layer-1 KILL
    short-circuits: no panel, no cost, a named reason."""
    pre = precheck(candidate, criteria, meta or {})
    if pre.killed:
        return LayeredResult(verdict="KILL", confidence=1.0, layer="precheck",
                             reason=pre.reason, cost_usd=0.0, check=pre.hit.check)

    if panel is None:
        raise NotImplementedError(
            "no panel provided: this standalone drop ships no LLM judge. "
            "Pass panel=<your evaluate fn> for Layer 2.")
    result = panel(candidate, criteria, **panel_kwargs)

    verdict = getattr(result, "verdict", None) or (
        result.get("verdict") if isinstance(result, dict) else "KILL")
    confidence = getattr(result, "confidence", None)
    if confidence is None and isinstance(result, dict):
        confidence = result.get("confidence", 0.0)
    cost = getattr(result, "total_cost_usd", 0.0) or (
        result.get("total_cost_usd", 0.0) if isinstance(result, dict) else 0.0)
    kill_shots = getattr(result, "kill_shots", None) or []
    reason = kill_shots[0] if kill_shots else ""

    return LayeredResult(verdict=str(verdict), confidence=float(confidence or 0.0),
                         layer="panel", reason=reason, cost_usd=float(cost or 0.0),
                         panel_result=result)
