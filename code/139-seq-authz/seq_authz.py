#!/usr/bin/env python3
"""
seq_authz.py — a 120-line illustration of sequence-aware tool authorisation.

The point in one sentence: a tool call can be individually valid and still be
the wrong call, because it is wrong in the context of what the agent already did
this session. Point-in-time authorisation (allow/deny each request in isolation)
cannot see that. Sequence-aware authorisation judges the current call against the
*trace* of prior calls.

This is a teaching model, not a policy engine. The real, production-grade version
of this idea is AWS Dogwood (an open-source temporal extension of the Cedar policy
language, Apache 2.0, built on Metric First-Order Temporal Logic). Use that if you
want to ship it. This file exists so you can *feel* the difference in a few lines:
run it and watch a session where every single call passes a point-in-time check,
yet the sequence is a data exfiltration.

Provider-neutral: no vendor, no MCP transport, no framework. Stdlib only.

    python3 seq_authz.py
"""
from dataclasses import dataclass, field


@dataclass
class Call:
    """One tool call in a session trace."""
    tool: str
    resource: str = ""
    amount: int = 0
    human_approved: bool = False
    ok: bool = True  # did the call succeed


# ---------------------------------------------------------------------------
# POINT-IN-TIME authorisation: judge each call alone. This is what a per-request
# allow/deny check (a plain Cedar policy, a middleware guard, most RBAC) does.
# Each rule here is individually reasonable, and the agent's identity is allowed
# to use every one of these tools. So each call, on its own, is a yes.
# ---------------------------------------------------------------------------
ALLOWED_TOOLS = {"read", "write", "export", "send"}
MAX_SINGLE_TRANSFER = 10_000


def point_in_time(call: Call) -> tuple[bool, str]:
    if call.tool not in ALLOWED_TOOLS:
        return False, f"tool '{call.tool}' not in allow-list"
    if call.tool == "send" and call.amount > MAX_SINGLE_TRANSFER:
        return False, f"single transfer {call.amount} over cap {MAX_SINGLE_TRANSFER}"
    return True, "allowed (looks fine in isolation)"


# ---------------------------------------------------------------------------
# SEQUENCE-AWARE authorisation: judge the current call against the trace of what
# already happened this session. Each rule below is a temporal condition — it
# refers to prior events, not just this request. (These four mirror the pattern
# families AWS Dogwood ships: workflow-ordering, stop-after, human-approval-gate,
# aggregate-limit.)
# ---------------------------------------------------------------------------
AGGREGATE_TRANSFER_LIMIT = 15_000


def sequence_aware(call: Call, trace: list[Call]) -> tuple[bool, str]:
    # First, it must still pass the point-in-time check. Sequence-aware is a
    # superset, never a bypass.
    ok, why = point_in_time(call)
    if not ok:
        return False, f"point-in-time: {why}"

    # 1. Workflow ordering: may only write a resource it has successfully read
    #    this session. Acting on state you never observed is the classic bug.
    if call.tool == "write":
        read_ok = any(c.tool == "read" and c.resource == call.resource and c.ok
                      for c in trace)
        if not read_ok:
            return False, f"write to '{call.resource}' before any successful read of it"

    # 2. Stop-after: once a bulk export has fired, no outbound send may follow.
    #    Read-all-then-send-out is the shape of exfiltration, even when each
    #    step is individually permitted.
    if call.tool == "send":
        if any(c.tool == "export" for c in trace):
            return False, "send after a bulk export in the same session (exfiltration shape)"

    # 3. Human-approval gate as a checkable precondition, not a UI hope: an
    #    outbound send is denied unless a human-approved event precedes it.
    if call.tool == "send":
        if not any(c.human_approved for c in trace) and not call.human_approved:
            return False, "outbound send with no human-approval event in the trace"

    # 4. Aggregate limit: the sum of transfers across the session may not exceed
    #    the cap, so one big action cannot be split into many allowed small ones.
    if call.tool == "send":
        spent = sum(c.amount for c in trace if c.tool == "send")
        if spent + call.amount > AGGREGATE_TRANSFER_LIMIT:
            return False, (f"aggregate transfers {spent + call.amount} over "
                           f"session cap {AGGREGATE_TRANSFER_LIMIT}")

    return True, "allowed (valid given the whole session)"


def run(session: list[Call]) -> None:
    """Replay a session under both models, side by side."""
    print(f"\n  {'STEP':<5}{'CALL':<34}{'POINT-IN-TIME':<16}{'SEQUENCE-AWARE'}")
    print("  " + "-" * 78)
    trace: list[Call] = []
    for i, call in enumerate(session, 1):
        desc = call.tool + (f" {call.resource}" if call.resource else "")
        desc += f" £{call.amount}" if call.amount else ""
        pit_ok, _ = point_in_time(call)
        seq_ok, seq_why = sequence_aware(call, trace)
        pit = "ALLOW" if pit_ok else "DENY"
        seq = "ALLOW" if seq_ok else "DENY"
        flag = "   <-- caught here" if (pit_ok and not seq_ok) else ""
        print(f"  {i:<5}{desc:<34}{pit:<16}{seq}{flag}")
        if not seq_ok:
            print(f"       reason: {seq_why}")
        # In a real system the denied call never executes. Here we let the
        # session continue so the whole story prints.
        trace.append(call)
    print()


if __name__ == "__main__":
    # A session where EVERY call passes the point-in-time check. The agent is
    # allowed to read, allowed to export, allowed to send under the cap. Nothing
    # here trips a per-request guard. And yet, read customer data, bulk export
    # it, then send it out, is an exfiltration. Only the sequence sees it.
    exfiltration = [
        Call("read", resource="customers", ok=True),
        Call("export", resource="customers", ok=True),
        Call("send", resource="external", amount=500, human_approved=True),
    ]
    print("\n  SCENARIO A — every call individually allowed, sequence is exfiltration")
    run(exfiltration)

    # A second session: an agent tries to write a record it never read, then
    # splits a large transfer into small allowed chunks to beat the single-call
    # cap. Point-in-time waves both through. Sequence-aware stops both.
    valid_but_wrong = [
        Call("write", resource="ledger"),                       # never read ledger
        Call("read", resource="ledger", ok=True),
        Call("send", resource="acct", amount=9_000, human_approved=True),
        Call("send", resource="acct", amount=9_000, human_approved=True),  # aggregate > cap
    ]
    print("  SCENARIO B — write-before-read, and a split transfer beating the single-call cap")
    run(valid_but_wrong)

    print("  Point-in-time asks: is THIS call allowed?  Sequence-aware asks:")
    print("  is this call allowed GIVEN everything the agent already did?\n")
