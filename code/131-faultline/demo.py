#!/usr/bin/env python3
"""Faultline demo — turn a KILL into a named, fixable cause.

Runs three trajectories through attribution and prints what each one blames.
No network, no dependencies, a few milliseconds. Run: python3 demo.py
"""
from faultline import Trajectory, attribute, attribute_kill, GYM_EXPLOIT


def show(title: str, att) -> None:
    print(f"\n=== {title} ===")
    print(f"  blame     : {att.primary.value}  (confidence {att.confidence:.2f})")
    print(f"  because   : {att.rationale}")
    print(f"  fix       : {att.refinement}")
    if att.secondary:
        print(f"  secondary : {att.secondary.value}  (this failure has happened before)")
    print("  ranking   :")
    for artifact, score in att.ranking:
        mark = "  <-- fix this" if artifact is att.primary else ""
        print(f"    {artifact.value:<14} {score:>4.1f}{mark}")


# 1. The worked example: the Melbourne gym-booking agent (OpenClaw + Claude).
#    Asked to book a full class, it found the cancel endpoint had no ownership
#    check and cancelled a stranger's slot. Total authorization bypass; the
#    prize was one waitlist place.
show("The gym-booking agent", attribute(GYM_EXPLOIT))

# 2. A different failure mode: the agent did something no rule forbade.
missing_rule = Trajectory(
    task="tidy the shared drive",
    failure="the agent deleted files it did not own; nothing in the policy forbade it",
)
show("A missing rule", attribute(missing_rule))

# 3. A repeat: the same failure has been seen before, so safety memory is
#    flagged as a secondary cause on top of the structural one.
repeat = Trajectory(
    action="POST /reservations/{id}/cancel",
    failure="cancelled another user's booking through the cancel endpoint with no auth check",
    prior_failures=("cancelled another user's booking via the unauthenticated cancel endpoint",),
)
show("A repeat failure", attribute(repeat))

# 4. The wiring point: attribution fires only on a KILL. A PASS has nothing to
#    evolve, so attribute_kill returns None and spends nothing.
print("\n=== The gate ===")
passed = attribute_kill({"verdict": "PASS", "reason": "output looks fine"})
killed = attribute_kill({"verdict": "KILL",
                         "reason": "any authenticated user could cancel another user's booking with no authorization check"})
print(f"  PASS -> {passed}")
print(f"  KILL -> blame {killed.primary.value}, fix scoped to the tool")

print("\nAttribution is the difference between 'it failed' and 'the tool policy failed, scope endpoint X'.")
