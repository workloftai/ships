"""Tests for Vera attribution (SHE trajectory-driven harness evolution).
No network: attribution is deterministic; the LLM path is stubbed."""
from __future__ import annotations

from faultline import (
    Artifact,
    Trajectory,
    attribute,
    attribute_kill,
    GYM_EXPLOIT,
    DEFINITIONS,
)


# --- the worked example: the gym exploit is unambiguously tool-policy --------

def test_gym_exploit_attributes_to_tool_policy():
    att = attribute(GYM_EXPLOIT)
    assert att.primary is Artifact.TOOL_POLICY
    assert att.confidence >= 0.6
    # the refinement must talk about scoping the tool, not adding a prompt rule
    assert "scope" in att.refinement.lower()


def test_gym_exploit_not_pinned_on_the_prompt():
    # the durable fix is structural; attribution must not blame the system prompt
    att = attribute(GYM_EXPLOIT)
    assert att.primary is not Artifact.SYSTEM_PROMPT


# --- each artifact owns its failure signature -------------------------------

def test_missing_rule_attributes_to_rule_bank():
    traj = Trajectory(
        failure="the agent did a thing no rule forbade; nothing in the policy covered it",
        task="tidy the shared drive",
    )
    assert attribute(traj).primary is Artifact.RULE_BANK


def test_scope_creep_attributes_to_system_prompt():
    traj = Trajectory(
        failure="the agent acted outside its remit and overstepped its scope",
        task="summarise the inbox",
    )
    assert attribute(traj).primary is Artifact.SYSTEM_PROMPT


def test_repeat_failure_flags_safety_memory():
    traj = Trajectory(
        failure="the same mistake happened again, as before",
        task="post the digest",
    )
    att = attribute(traj)
    assert att.recurrence is True


def test_recurrence_via_prior_failures_sets_secondary():
    prior = "cancelled another user's booking via the unauthenticated cancel endpoint"
    traj = Trajectory(
        failure="cancelled another user's booking through the cancel endpoint with no auth check",
        action="POST /reservations/{id}/cancel",
        prior_failures=(prior,),
    )
    att = attribute(traj)
    assert att.recurrence is True
    # primary is still the structural artifact; memory is the secondary
    assert att.primary is Artifact.TOOL_POLICY
    assert att.secondary is Artifact.SAFETY_MEMORY


# --- ranking + tie-break honesty --------------------------------------------

def test_ranking_covers_all_four_artifacts():
    att = attribute(GYM_EXPLOIT)
    assert {a for a, _ in att.ranking} == set(Artifact)
    # sorted high to low
    scores = [s for _, s in att.ranking]
    assert scores == sorted(scores, reverse=True)


def test_no_signal_defaults_to_structural_low_confidence():
    att = attribute(Trajectory(failure="something went wrong somewhere"))
    assert att.primary is Artifact.TOOL_POLICY  # most structural default
    assert att.confidence == 0.0


def test_tie_break_prefers_tool_policy():
    # craft a failure that trips one tool-policy and one system-prompt signal at
    # equal weight; durability order must hand the tie to tool-policy
    traj = Trajectory(
        failure="the agent was not asked to, but any authenticated user could act",
    )
    att = attribute(traj)
    assert att.primary is Artifact.TOOL_POLICY


# --- the LLM path is injectable and falls back safely -----------------------

def test_llm_override_is_used_when_present():
    def fake_llm(traj):
        return (Artifact.RULE_BANK, "model says a rule was missing", "add the rule", 0.9)

    att = attribute(GYM_EXPLOIT, llm=fake_llm)
    assert att.primary is Artifact.RULE_BANK
    assert att.source == "llm"
    assert att.confidence == 0.9


def test_llm_failure_falls_back_to_heuristic():
    def broken_llm(traj):
        raise RuntimeError("model down")

    att = attribute(GYM_EXPLOIT, llm=broken_llm)
    assert att.source == "heuristic"
    assert att.primary is Artifact.TOOL_POLICY


def test_llm_none_falls_back_to_heuristic():
    att = attribute(GYM_EXPLOIT, llm=lambda t: None)
    assert att.source == "heuristic"
    assert att.primary is Artifact.TOOL_POLICY


# --- the wiring point: attribute only on a KILL -----------------------------

def test_attribute_kill_returns_none_on_pass():
    assert attribute_kill({"verdict": "PASS", "reason": "looks fine"}) is None


def test_attribute_kill_attributes_on_kill():
    res = {"verdict": "KILL", "reason": "any authenticated user could cancel another user's booking with no authorization check"}
    att = attribute_kill(res)
    assert att is not None
    assert att.primary is Artifact.TOOL_POLICY


def test_attribute_kill_uses_supplied_trajectory():
    res = {"verdict": "KILL", "reason": "short reason"}
    att = attribute_kill(res, GYM_EXPLOIT)
    assert att is not None and att.primary is Artifact.TOOL_POLICY


# --- definitions are complete -----------------------------------------------

def test_every_artifact_has_a_definition():
    assert set(DEFINITIONS) == set(Artifact)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
