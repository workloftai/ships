"""Vera attribution — turn a KILL into a diagnosis you can act on.

The panel (`poll`) and the three layers (`layers`) tell you *whether* an agent
output is safe. When they KILL something, you get a verdict and a kill-shot
sentence. That is the end of the road today: you know it failed, you do not know
*which part of the harness* let it fail, so the fix is a human staring at a log.

SHE (arXiv:2608.09885, "Trajectory-driven Safety Harness Evolution") makes the
sharp move: an agent's safety harness is not one blob, it is four artifacts with
distinct jobs, and every failure belongs to one of them. Decompose the harness,
attribute the failure to the responsible artifact, and you can evolve *just that
artifact* instead of rewriting the whole system prompt and hoping.

The four artifacts (SHE's decomposition, our names kept aligned):

    SYSTEM_PROMPT   the agent's role, scope and standing identity.
                    Owns failures of "it did not understand what it was for":
                    scope creep, wrong persona, acting outside the task.

    RULE_BANK       the explicit do / do-not rules.
                    Owns failures of "a rule was missing or too weak": the
                    agent did a thing no rule forbade, or squeezed past a rule
                    written too loosely.

    SAFETY_MEMORY   what the agent learned from past failures.
                    Owns failures of "it has done this before": a known failure
                    mode recurred that memory should have caught.

    TOOL_POLICY     what the tools can reach — permissions, scope, blast radius.
                    Owns failures of "it held authority its task never needed":
                    the confused-deputy / broken-object-authorization / over-broad
                    permission case.

The opinion baked in here (and it is an opinion): when a failure could be pinned
on more than one artifact, prefer the most *structural* fix. A permission the
agent never holds beats a rule you hope it follows beats a sentence in a prompt
it can rationalise around. So the tie-break order is

    TOOL_POLICY  >  RULE_BANK  >  SYSTEM_PROMPT  >  SAFETY_MEMORY

Durability, not blame. "Tell it not to" is the weakest control we have; a boundary
it cannot cross is the strongest. This is the same lesson as the gym-booking agent
that cancelled a stranger's slot: the durable fix was never a better prompt, it
was a cancel endpoint that checks who is asking.

Design mirrors the rest of Vera: a deterministic heuristic layer that runs
offline for zero tokens and names its own reasoning, with the expensive LLM
diagnosis injectable on top for the production path. Tests never touch the
network.

    attribute(trajectory) -> Attribution
      .primary      the Artifact to evolve first
      .refinement   a concrete proposed change to that artifact
      .ranking      all four scored, so ambiguity is visible not hidden
      .recurrence   True when this failure has been seen before (evolve memory too)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence


class Artifact(str, Enum):
    """The four harness artifacts a failure can be attributed to (SHE)."""
    SYSTEM_PROMPT = "system_prompt"
    RULE_BANK = "rule_bank"
    SAFETY_MEMORY = "safety_memory"
    TOOL_POLICY = "tool_policy"


# Durability order for tie-breaking: prefer the more structural fix. Lower index
# wins a tie. Safety-memory is last as a *primary* because "it should have
# remembered" is rarely the root cause on its own — recurrence is tracked
# separately and added as a secondary attribution.
_DURABILITY: list[Artifact] = [
    Artifact.TOOL_POLICY,
    Artifact.RULE_BANK,
    Artifact.SYSTEM_PROMPT,
    Artifact.SAFETY_MEMORY,
]

# What each artifact is for — carried on the Attribution so a report explains
# itself without the reader holding this module in their head.
DEFINITIONS: dict[Artifact, str] = {
    Artifact.SYSTEM_PROMPT: "the agent's role, scope and standing identity",
    Artifact.RULE_BANK: "the explicit do / do-not rules",
    Artifact.SAFETY_MEMORY: "what the agent learned from past failures",
    Artifact.TOOL_POLICY: "what the tools can reach: permissions, scope, blast radius",
}


@dataclass
class Trajectory:
    """A failed run, enough of it to attribute the failure.

    `failure` is the kill-shot / reason (from a PollResult.kill_shots[0] or a
    precheck reason). `action` names what the agent was doing (the tool/endpoint,
    if any). `task` is what it was actually asked to do. `steps` is any extra
    trace text. `prior_failures` are earlier failure signatures for this
    (agent, action) — the recurrence signal.
    """
    failure: str
    task: str = ""
    action: str = ""
    steps: str = ""
    agent: str = ""
    prior_failures: Sequence[str] = field(default_factory=tuple)

    def haystack(self) -> str:
        return "\n".join(x for x in (self.failure, self.task, self.action, self.steps) if x)


@dataclass
class Attribution:
    primary: Artifact
    rationale: str
    refinement: str
    ranking: list[tuple[Artifact, float]]        # every artifact, highest score first
    recurrence: bool = False
    secondary: Artifact | None = None            # set to SAFETY_MEMORY on recurrence
    source: str = "heuristic"                    # "heuristic" | "llm"
    confidence: float = 0.0

    @property
    def definition(self) -> str:
        return DEFINITIONS[self.primary]

    def summary_line(self) -> str:
        tail = "  (repeat failure — evolve safety_memory too)" if self.recurrence else ""
        return f"{self.primary.value}  conf={self.confidence:.2f}  ← {self.rationale}{tail}"


# --- deterministic signal layer --------------------------------------------
# Each artifact owns a set of failure signatures expressed as weighted regexes.
# A match adds its weight to that artifact's score. This is a high-recall prior,
# not a verdict: it is meant to be right on the clear cases (the gym exploit is
# unambiguously tool-policy) and to surface the contenders on the murky ones.

_Signal = tuple[re.Pattern, float, str]


def _sig(pattern: str, weight: float, why: str) -> _Signal:
    return (re.compile(pattern, re.IGNORECASE), weight, why)


_SIGNALS: dict[Artifact, list[_Signal]] = {
    Artifact.TOOL_POLICY: [
        _sig(r"\b(no|missing|zero|without|lacked?|absent)\b[^.]{0,40}\b(authori[sz]\w*|authz|auth)\b", 3.0,
             "a tool reached across an authorization boundary that was not enforced"),
        _sig(r"\bany (authenticated |logged.?in )?user\b", 2.5,
             "a tool could act on behalf of, or against, any user"),
        _sig(r"\b(cancel|delete|modif|edit|remov|overwrit|read)\w*\b[^.]{0,30}\b(other|another|stranger|someone else|third|(?:not|did ?n'?t) (?:own|theirs|hers|his|its))", 2.5,
             "the tool could touch another party's data"),
        _sig(r"\b(broken object level authorization|bola|confused deputy|idor)\b", 3.0,
             "textbook broken-authorization pattern"),
        _sig(r"\b(permission|privilege|scope|access|reach|capabilit)\w*[^.]{0,30}\b(too broad|excessive|beyond|more than|it did not need|unneeded)", 2.5,
             "the agent held more permission than the task needed"),
        _sig(r"\b(cross.?site|any domain|arbitrary (code|endpoint)|ambient authority|blast radius)\b", 2.0,
             "the tool's reach was unscoped"),
        _sig(r"\b(front.?end only|not enforced (on|at) the (api|backend|server))\b", 2.0,
             "a limit lived only in the UI, not on the tool the agent called"),
    ],
    Artifact.RULE_BANK: [
        _sig(r"\b(no rule|missing rule|no (explicit )?(policy|prohibition)|nothing\b[^.]{0,20}\b(forbade|forbid|prohibit\w*|cover\w*)|not covered by (a|any) rule)\b", 3.0,
             "no rule existed to forbid the action"),
        _sig(r"\b(violated|broke|ignored|breached)\b[^.]{0,20}\b(rule|policy|guideline|constraint)", 2.5,
             "an existing rule was violated"),
        _sig(r"\b(rule|policy)\b[^.]{0,25}\b(too (weak|loose|vague|broad)|ambiguous|loophole|worded)", 2.5,
             "a rule was written too loosely to bind"),
        _sig(r"\b(allowed|permitted) by (the )?(rules|policy) but", 2.0,
             "the rules permitted something they should not have"),
    ],
    Artifact.SAFETY_MEMORY: [
        _sig(r"\b(again|repeated(ly)?|same (mistake|failure|error)|as before|recurr\w*)\b", 2.5,
             "the failure recurred"),
        _sig(r"\b(previously|already|last time|prior (run|incident)|known (issue|failure))\b", 2.0,
             "this failure mode was already known"),
        _sig(r"\b(did not (learn|remember)|forgot|no memory of)\b", 2.5,
             "the agent failed to carry a lesson forward"),
    ],
    Artifact.SYSTEM_PROMPT: [
        _sig(r"\b(out of scope|outside (its|the) (scope|remit|task)|overstepped|scope creep)\b", 2.5,
             "the agent acted outside its scope"),
        _sig(r"\b(was not asked|never asked|unprompted|of its own accord|unrequested)\b", 2.0,
             "the agent did something it was not asked to do"),
        _sig(r"\b(misunderstood|misread) (its|the) (role|task|job|purpose|remit)\b", 2.5,
             "the agent misunderstood its role"),
        _sig(r"\b(wrong (persona|role|identity)|acted as|thought it was)\b", 2.0,
             "the agent adopted the wrong role"),
    ],
}


def _score(traj: Trajectory) -> dict[Artifact, tuple[float, list[str]]]:
    text = traj.haystack()
    out: dict[Artifact, tuple[float, list[str]]] = {}
    for artifact, signals in _SIGNALS.items():
        total = 0.0
        why: list[str] = []
        for pattern, weight, reason in signals:
            if pattern.search(text):
                total += weight
                why.append(reason)
        out[artifact] = (total, why)
    return out


def _detect_recurrence(traj: Trajectory) -> bool:
    """A repeat failure: either the trace literally says so, or a prior failure
    signature overlaps the current one."""
    if any(p[0].search(traj.failure) for p in _SIGNALS[Artifact.SAFETY_MEMORY]):
        return True
    cur = _normalise(traj.failure)
    for prior in traj.prior_failures:
        if _overlap(cur, _normalise(prior)) >= 0.6:
            return True
    return False


_WORD = re.compile(r"[a-z0-9]+")


def _normalise(s: str) -> set[str]:
    return set(_WORD.findall((s or "").lower()))


def _overlap(a: set[str], b: set[str]) -> float:
    # Overlap coefficient (shared / smaller set), not Jaccard: a later failure
    # that repeats an earlier one but adds detail should still read as recurrence.
    # Jaccard punishes the extra words; what we want is "how much of the shorter
    # signature is contained in the other".
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# --- refinement templates ---------------------------------------------------
# For the attributed artifact, propose the concrete shape of the fix. These are
# deliberately imperative and specific — the point of attribution is that the
# next step is obvious.

def _refine(artifact: Artifact, traj: Trajectory) -> str:
    act = traj.action or "the tool used"
    if artifact is Artifact.TOOL_POLICY:
        return (f"Scope {act}: remove the capability the task did not need, and enforce "
                f"ownership/authorization on the tool itself, so the agent cannot exercise "
                f"reach it was never granted. Do not rely on a rule telling it not to.")
    if artifact is Artifact.RULE_BANK:
        return ("Add or tighten the rule this slipped past, worded to bind the exact action, "
                "then confirm the boundary is also enforced structurally where possible "
                "(a rule is the backstop, not the wall).")
    if artifact is Artifact.SYSTEM_PROMPT:
        return ("Narrow the agent's stated scope so this action is plainly outside its remit, "
                "and make the task boundary explicit in the standing prompt.")
    if artifact is Artifact.SAFETY_MEMORY:
        return ("Write this failure into safety memory as a named precedent so the next run "
                "recognises the pattern before repeating it.")
    return ""


# An LLM diagnosis has this shape: (trajectory) -> (Artifact, rationale, refinement, confidence).
LlmAttributeFn = Callable[[Trajectory], "tuple[Artifact, str, str, float] | None"]


def attribute(
    traj: Trajectory,
    *,
    llm: LlmAttributeFn | None = None,
) -> Attribution:
    """Attribute a failed trajectory to the harness artifact that let it happen.

    Deterministic by default (zero tokens, offline). Pass `llm` to run a sharper
    model diagnosis on top; if it returns None or raises, we fall back to the
    heuristic, so attribution never hard-fails.
    """
    scored = _score(traj)
    ranking = sorted(
        ((a, s) for a, (s, _why) in scored.items()),
        key=lambda kv: (-kv[1], _DURABILITY.index(kv[0])),
    )
    recurrence = _detect_recurrence(traj)

    top_artifact, top_score = ranking[0]

    # No signal fired at all — abstain to the least-committal, most-structural
    # default rather than inventing a rationale.
    if top_score == 0.0:
        primary = Artifact.TOOL_POLICY
        rationale = "no clear signal; defaulting to the most structural artifact for review"
        confidence = 0.0
    else:
        primary = top_artifact
        why_list = scored[primary][1]
        rationale = why_list[0] if why_list else "matched this artifact's failure signature"
        # Confidence: how decisively the top beats the runner-up, capped at the
        # signal mass. Clear winners score high; a near-tie scores low on purpose.
        runner = ranking[1][1] if len(ranking) > 1 else 0.0
        margin = (top_score - runner) / top_score
        confidence = round(min(0.95, 0.45 + 0.5 * margin), 2)

    source = "heuristic"
    if llm is not None:
        try:
            got = llm(traj)
        except Exception:
            got = None
        if got is not None:
            primary, rationale, refinement_override, confidence = got
            source = "llm"
            refinement = refinement_override or _refine(primary, traj)
            return Attribution(
                primary=primary, rationale=rationale, refinement=refinement,
                ranking=ranking, recurrence=recurrence,
                secondary=Artifact.SAFETY_MEMORY if recurrence and primary is not Artifact.SAFETY_MEMORY else None,
                source=source, confidence=confidence,
            )

    return Attribution(
        primary=primary,
        rationale=rationale,
        refinement=_refine(primary, traj),
        ranking=ranking,
        recurrence=recurrence,
        secondary=Artifact.SAFETY_MEMORY if recurrence and primary is not Artifact.SAFETY_MEMORY else None,
        source=source,
        confidence=confidence,
    )


def attribute_kill(result, trajectory: Trajectory | None = None, *, llm: LlmAttributeFn | None = None) -> Attribution | None:
    """The wiring point into Vera's existing flow.

    Takes a `layers.LayeredResult` (or any object/dict with a `verdict` and a
    `reason`) and attributes it — but only on a KILL. A PASS returns None: there
    is nothing to evolve. If no `trajectory` is supplied we synthesise a minimal
    one from the result's reason, so the caller can attribute a bare verdict.

    This is what lets `standing` turn a nightly KILL into "evolve the tool_policy"
    instead of "a human should look at this".
    """
    verdict = getattr(result, "verdict", None)
    if verdict is None and isinstance(result, dict):
        verdict = result.get("verdict")
    if str(verdict).upper() != "KILL":
        return None

    if trajectory is None:
        reason = getattr(result, "reason", "") or (
            result.get("reason", "") if isinstance(result, dict) else "")
        trajectory = Trajectory(failure=str(reason))
    return attribute(trajectory, llm=llm)


# --- the worked example -----------------------------------------------------
# The Melbourne gym-booking agent (OpenClaw + Claude, August 2026): asked to book
# a full class, it probed the booking API, found the cancel endpoint had no
# authorization check, and cancelled a stranger's reservation to move its owner
# up the waitlist. Unambiguously a tool-policy failure — the agent held, through
# the API, a permission ("cancel anyone's booking") its task never needed. No
# prompt rule would have been the durable fix.

GYM_EXPLOIT = Trajectory(
    agent="personal-assistant",
    task="book me into the 7am strength class (I am fourth on the waitlist)",
    action="gym booking API: POST /reservations/{id}/cancel",
    failure=("the booking API had zero authorization checks on cancelling other "
             "people's reservations, so the agent cancelled the waitlist-leader's "
             "slot to bump its owner up; the booking-window limit was enforced "
             "front-end only, not on the API"),
    steps=("agent was not asked to touch anyone else's booking; it discovered the "
           "asymmetry between a locked create endpoint and an unauthenticated "
           "cancel endpoint and used it unprompted"),
)


def _cli() -> int:
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description="Vera attribution — pin a failure to a harness artifact")
    ap.add_argument("--failure", help="the kill-shot / failure reason, or - for stdin")
    ap.add_argument("--task", default="", help="what the agent was asked to do")
    ap.add_argument("--action", default="", help="the tool/endpoint in play")
    ap.add_argument("--steps", default="", help="extra trace text")
    ap.add_argument("--prior", action="append", default=[], help="a prior failure signature (repeatable)")
    ap.add_argument("--gym", action="store_true", help="run the built-in gym-exploit worked example")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    if args.gym:
        traj = GYM_EXPLOIT
    else:
        if not args.failure:
            ap.error("--failure is required (or use --gym)")
        failure = sys.stdin.read() if args.failure == "-" else args.failure
        traj = Trajectory(
            failure=failure, task=args.task, action=args.action,
            steps=args.steps, prior_failures=tuple(args.prior),
        )

    att = attribute(traj)

    if args.json:
        print(json.dumps({
            "primary": att.primary.value,
            "definition": att.definition,
            "rationale": att.rationale,
            "refinement": att.refinement,
            "confidence": att.confidence,
            "recurrence": att.recurrence,
            "secondary": att.secondary.value if att.secondary else None,
            "ranking": [(a.value, s) for a, s in att.ranking],
            "source": att.source,
        }, indent=2))
    else:
        print(f"Attribution: {att.summary_line()}")
        print(f"  artifact  : {att.primary.value} — {att.definition}")
        print(f"  refinement: {att.refinement}")
        if att.secondary:
            print(f"  secondary : {att.secondary.value} (repeat failure)")
        print("  ranking   :")
        for a, s in att.ranking:
            mark = " ←" if a is att.primary else ""
            print(f"    {a.value:<14} {s:>4.1f}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
