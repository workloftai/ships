"""Vera Layer 1 — deterministic programmatic pre-check.

The Airbnb three-layer eval model (programmatic → LLM judge → human calibration)
starts with a layer Vera never had: cheap, deterministic checks that run BEFORE
any LLM-judge tokens are spent. Vera today jumps straight to the panel (or the
`screen` triage), so it pays juror cost to reject outputs that a regex could kill
for free.

The sharp rule this layer encodes: **a cheap PASS is the vibe trap, a cheap KILL
is free money.** So Layer 1 only ever emits KILL or ABSTAIN, never PASS. A real
PASS still has to earn the panel. Programmatic checks are high-precision refusals
of things that are obviously wrong — an empty output, a raw traceback, an
unmarked failure — not a shortcut to approval.

The motivating case is live: the Loop board keeps filling with Vera flags of the
shape "the call has success=false, and there is no evidence that this failure is
an expected part of the process" (the FOLLOWING axis). That is a deterministic
signal. Catching it here means the panel never has to convene for it.

Design:
  precheck(candidate, criteria, meta=None) -> PrecheckResult
    verdict is "KILL"  (a check fired, short-circuit, spend no juror tokens)
             or "ABSTAIN" (nothing fired, fall through to the LLM panel)

Each check is a small pure function (candidate, criteria, meta) -> Hit | None.
Checks are ordered; the first KILL wins and names itself, so a Layer-1 kill is
always explainable ("killed by unmarked_failure", not "the model said so").
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------

# Tokens that mark a failure as an EXPECTED, handled part of the flow. If any of
# these is present near a success=false, the failure is by-design, not a fault —
# so the unmarked_failure check abstains. Kept deliberately broad; a false
# abstain just falls through to the panel, which is the safe direction.
_EXPECTED_FAILURE_MARKERS = re.compile(
    r"\b(expected|intended|by design|as designed|deliberate(?:ly)?|"
    r"graceful(?:ly)?|handled|caught|fallback|retr(?:y|ied|ying)|"
    r"anticipated|planned failure|known limitation|no[- ]op|skipped)\b",
    re.IGNORECASE,
)

# Criteria wording that says a failure/None/empty result is an acceptable outcome.
_FAILURE_OK_IN_CRITERIA = re.compile(
    r"\b(failure is (?:ok|acceptable|fine|allowed|expected)|"
    r"may (?:fail|return (?:none|empty|null))|"
    r"empty (?:is )?(?:ok|acceptable|allowed)|"
    r"can be empty|null is valid)\b",
    re.IGNORECASE,
)

# A raw, unhandled error leaking into an output the agent presented as its answer.
_TRACEBACK = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)
_UNHANDLED_EXC = re.compile(
    r"\b([A-Z][A-Za-z]*Error|[A-Z][A-Za-z]*Exception):\s", )

# Criteria that demands structured/JSON output.
_WANTS_JSON = re.compile(r"\b(strict )?json\b|structured output", re.IGNORECASE)

_EMPTYISH = {"", "null", "none", "n/a", "na", "undefined", "[]", "{}", "()"}


@dataclass
class Hit:
    """One programmatic check firing a KILL."""
    check: str
    reason: str


@dataclass
class PrecheckResult:
    verdict: str                       # "KILL" | "ABSTAIN"
    hit: Hit | None = None
    checks_run: list[str] = field(default_factory=list)

    @property
    def killed(self) -> bool:
        return self.verdict == "KILL"

    @property
    def reason(self) -> str:
        return self.hit.reason if self.hit else ""


# --- the checks -------------------------------------------------------------
# Each takes (candidate, criteria, meta) and returns a Hit to KILL, or None to
# abstain. `candidate` is the output text under review; `meta` is the optional
# structured context (e.g. an audit row) — a check reads whichever it needs.

def _check_empty(candidate: str, criteria: str, meta: dict) -> Hit | None:
    stripped = (candidate or "").strip()
    if stripped.lower() in _EMPTYISH:
        if _FAILURE_OK_IN_CRITERIA.search(criteria or ""):
            return None  # criteria explicitly allows an empty result
        return Hit("empty_output", "output is empty or a bare null/none placeholder")
    return None


def _coerce_success(candidate: str, meta: dict) -> bool | None:
    """Find a success flag in meta, or in the candidate if it is JSON. Returns
    True/False, or None when there is no explicit success signal to judge."""
    if isinstance(meta, dict):
        for key in ("success", "ok", "succeeded"):
            if key in meta and isinstance(meta[key], bool):
                return meta[key]
    text = (candidate or "").strip()
    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            return None
        for key in ("success", "ok", "succeeded"):
            if isinstance(obj.get(key), bool):
                return obj[key]
    return None


def _check_unmarked_failure(candidate: str, criteria: str, meta: dict) -> Hit | None:
    """The live one: success=false with no evidence the failure is expected.

    This is the FOLLOWING-axis pattern that keeps reaching the panel. If the
    call failed and neither the output nor the criteria frame that failure as a
    designed, handled outcome, it is a fault — kill it here."""
    success = _coerce_success(candidate, meta)
    if success is not False:
        return None
    haystack = f"{candidate}\n{criteria}"
    if _EXPECTED_FAILURE_MARKERS.search(haystack):
        return None
    if _FAILURE_OK_IN_CRITERIA.search(criteria or ""):
        return None
    return Hit(
        "unmarked_failure",
        "call reports success=false with no evidence the failure is an expected, "
        "handled part of the process",
    )


def _check_error_leak(candidate: str, criteria: str, meta: dict) -> Hit | None:
    text = candidate or ""
    if _TRACEBACK.search(text):
        return Hit("error_leak", "raw traceback leaked into the presented output")
    # An unhandled-exception repr, but not when the criteria is about error text
    # (e.g. "explain what a ValueError is") — then the token is legitimately part
    # of the answer.
    if _UNHANDLED_EXC.search(text) and not re.search(
        r"error|exception|traceback", criteria or "", re.IGNORECASE
    ):
        return Hit("error_leak", "unhandled exception repr in the presented output")
    return None


def _check_schema(candidate: str, criteria: str, meta: dict) -> Hit | None:
    if not _WANTS_JSON.search(criteria or ""):
        return None
    text = (candidate or "").strip()
    # tolerate a ```json fence
    fence = re.match(r"^```(?:json)?\s*(.+?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if not text:
        return None  # empty is handled by _check_empty
    try:
        json.loads(text)
    except (ValueError, TypeError):
        return Hit("schema_violation", "criteria requires JSON but output does not parse as JSON")
    return None


# Order matters: cheapest / most decisive first. First KILL wins.
CHECKS: list[Callable[[str, str, dict], "Hit | None"]] = [
    _check_empty,
    _check_unmarked_failure,
    _check_error_leak,
    _check_schema,
]


def precheck(candidate: str, criteria: str = "", meta: dict | None = None) -> PrecheckResult:
    """Run Layer 1. Returns KILL (a check fired) or ABSTAIN (fall through to the
    LLM panel). Never returns PASS by design — a cheap PASS is the vibe trap."""
    meta = meta or {}
    run: list[str] = []
    for check in CHECKS:
        run.append(check.__name__.removeprefix("_check_"))
        hit = check(candidate, criteria, meta)
        if hit is not None:
            return PrecheckResult(verdict="KILL", hit=hit, checks_run=run)
    return PrecheckResult(verdict="ABSTAIN", checks_run=run)


def _cli() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Vera Layer 1 programmatic pre-check")
    ap.add_argument("--candidate", required=True, help="output under review, or - for stdin")
    ap.add_argument("--criteria", default="", help="the rubric / what good looks like")
    ap.add_argument("--meta", default="", help="optional JSON of structured context (audit row)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    candidate = sys.stdin.read() if args.candidate == "-" else args.candidate
    meta = json.loads(args.meta) if args.meta else {}
    res = precheck(candidate, args.criteria, meta)

    if args.json:
        print(json.dumps({
            "verdict": res.verdict,
            "check": res.hit.check if res.hit else None,
            "reason": res.reason,
            "checks_run": res.checks_run,
        }))
    else:
        print(f"Layer 1: {res.verdict}")
        if res.killed:
            print(f"  killed by {res.hit.check}: {res.reason}")
        else:
            print(f"  nothing fired ({', '.join(res.checks_run)}) — fall through to the panel")
    # Exit 1 on a kill so a shell pipeline can short-circuit.
    return 1 if res.killed else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
