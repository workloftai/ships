"""
Cascade escalation policy for Larry's tier routing.

The base classifier (classifier.py) picks a starting tier by keyword. This
module decides whether a task should be escalated UP to the Astra tier
(Tier 4) — the frontier/spike lane — and whether that escalation needs a
human confirmation gate first.

Escalation is deliberately conservative: Astra is a $10/$50-per-Mtok model, and
our own eval (~/astra-eval) showed it only earns that premium in its spike
band. So we escalate on exactly three triggers, and nothing else:

  1. spike_band       — the task is in Astra's proven niche (browser/computer-
                        use, cyber/vuln, frontier-maths, >512K context).
                        Decided pre-attempt from the message text.
  2. tool_failures    — a lower tier has failed tool calls REPEATEDLY
                        (>= TOOL_FAILURE_THRESHOLD). Decided post-attempt.
  3. low_confidence   — a lower tier self-reported confidence below
                        LOW_CONFIDENCE_THRESHOLD. Decided post-attempt.

A cost guard caps how many times a single conversation can escalate to Astra
(MAX_ASTRA_ESCALATIONS) so a pathological loop can't drain the guardrail.

Confirmation gate (see #6): any Astra-routed task that also has write access to
shell / filesystem / browser must be confirmed (human or secondary model)
before it runs, because Astra is the first model rated "Critical" on cyber and
unconfirmed frontier tool-use carries a measurable misaligned-outcome rate.
"""

from dataclasses import dataclass, field

from classifier import ASTRA_TIER, spike_band

TOOL_FAILURE_THRESHOLD = 2      # >= this many failed tool calls at a lower tier
LOW_CONFIDENCE_THRESHOLD = 0.5  # self-reported confidence below this
MAX_ASTRA_ESCALATIONS = 3       # per conversation, cost backstop

# Tool tags that mean "can change the world" → confirmation gate when on Astra.
WRITE_ACCESS_TAGS = {
    "shell", "bash", "exec", "filesystem_write", "file_write", "write_file",
    "browser_write", "browser_action", "delete", "deploy", "network_write",
    "send_email", "payment",
}


@dataclass
class EscalationSignals:
    """Runtime signals fed into the escalation decision."""
    tool_failures: int = 0            # failed tool calls so far at lower tiers
    self_confidence: float = None     # last tier's self-reported confidence 0..1
    astra_escalations_so_far: int = 0  # how many times this conv already hit Astra
    task_tags: set = field(default_factory=set)  # capability tags for this task


def _spike_reason(message: str):
    cat = spike_band(message)
    return f"spike_band:{cat}" if cat else None


def should_escalate_to_astra(message: str, signals: EscalationSignals):
    """
    Decide whether to route this task to the Astra escalation lane.

    Returns (escalate: bool, reason: str|None).
    """
    # Cost backstop first: never exceed the per-conversation escalation cap.
    if signals.astra_escalations_so_far >= MAX_ASTRA_ESCALATIONS:
        return False, "escalation_cap_reached"

    reason = _spike_reason(message)
    if reason:
        return True, reason

    if signals.tool_failures >= TOOL_FAILURE_THRESHOLD:
        return True, f"repeated_tool_failure:{signals.tool_failures}"

    if (signals.self_confidence is not None
            and signals.self_confidence < LOW_CONFIDENCE_THRESHOLD):
        return True, f"low_confidence:{signals.self_confidence:.2f}"

    return False, None


def requires_confirmation(tier: int, signals: EscalationSignals):
    """
    Confirmation gate: True when routing to Astra AND the task can take a
    world-changing (write/exec) action. Returns (needs_confirmation, tags_hit).
    """
    if tier != ASTRA_TIER:
        return False, set()
    hit = signals.task_tags & WRITE_ACCESS_TAGS
    return (len(hit) > 0), hit


if __name__ == "__main__":
    cases = [
        # (message, signals, expect_escalate, expect_reason_prefix)
        ("What are your opening hours?", EscalationSignals(), False, None),
        ("Please browse the site and fill in the form for me",
         EscalationSignals(), True, "spike_band:browser_computer_use"),
        ("Reverse engineer this binary and find the vulnerability",
         EscalationSignals(), True, "spike_band:cyber_vuln"),
        ("Prove that there are infinitely many primes of this form",
         EscalationSignals(), True, "spike_band:frontier_maths"),
        ("Summarise this", EscalationSignals(tool_failures=2), True,
         "repeated_tool_failure"),
        ("Summarise this", EscalationSignals(tool_failures=1), False, None),
        ("Summarise this", EscalationSignals(self_confidence=0.3), True,
         "low_confidence"),
        ("Summarise this", EscalationSignals(self_confidence=0.9), False, None),
        ("Exploit the CVE", EscalationSignals(astra_escalations_so_far=3),
         False, "escalation_cap_reached"),
    ]
    ok = 0
    for msg, sig, exp_esc, exp_reason in cases:
        esc, reason = should_escalate_to_astra(msg, sig)
        good = esc == exp_esc and (
            exp_reason is None and reason is None
            or (exp_reason is not None and reason is not None and reason.startswith(exp_reason))
            or (not esc and exp_reason == reason)
        )
        ok += good
        print(f"[{'OK ' if good else 'FAIL'}] esc={esc!s:5} reason={reason!s:32} <- {msg[:45]}")

    print("\nConfirmation gate:")
    for tier, tags, exp in [
        (ASTRA_TIER, {"shell"}, True),
        (ASTRA_TIER, {"read_file"}, False),
        (ASTRA_TIER, {"read_file", "deploy"}, True),
        (2, {"shell"}, False),
    ]:
        needs, hit = requires_confirmation(tier, EscalationSignals(task_tags=tags))
        good = needs == exp
        ok += good
        print(f"[{'OK ' if good else 'FAIL'}] tier={tier} tags={tags} -> needs={needs} hit={hit}")

    total = len(cases) + 4
    print(f"\n{ok}/{total} passed")
    raise SystemExit(0 if ok == total else 1)
