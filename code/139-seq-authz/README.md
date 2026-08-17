# seq-authz — a valid tool call can still be the wrong one

Most agent authorisation is point-in-time: each tool call is allowed or denied on
its own. Identity checks out, the tool is on the allow-list, the arguments are in
range, so it fires. That is necessary and it is not enough. A call can be
individually valid and still be the wrong call, because it is wrong in the context
of what the agent already did this session.

Run the demo and watch it happen:

```
python3 seq_authz.py
```

```
SCENARIO A — every call individually allowed, sequence is exfiltration

STEP CALL                    POINT-IN-TIME   SEQUENCE-AWARE
1    read customers          ALLOW           ALLOW
2    export customers        ALLOW           ALLOW
3    send external £500       ALLOW           DENY   <-- caught here
     reason: send after a bulk export in the same session (exfiltration shape)
```

Read customer data, bulk-export it, send it out. Every step passes a per-request
check. The identity is allowed to read, allowed to export, allowed to send under
the cap. Nothing trips a point-in-time guard. And yet the sequence is a data
exfiltration. Only a check that looks at the *trace* of prior calls can see it.

## The idea

Point-in-time asks: *is this call allowed?* Sequence-aware asks: *is this call
allowed given everything the agent already did this session?* The second question
needs the history, so the policy has to be **temporal**, it refers to prior events,
not just the current request.

The demo carries four temporal rules, the same families a real temporal policy
engine ships:

- **Workflow ordering** — may write a record only after successfully reading it.
  Acting on state you never observed is the classic agent bug.
- **Stop-after** — no outbound send once a bulk export has fired. Read-all-then-
  send-out is the shape of exfiltration even when each step is permitted.
- **Human-approval gate as a precondition** — an outbound send is denied unless a
  human-approval event precedes it in the trace. Approval becomes a thing the
  engine verifies, not a dialog you hope was shown.
- **Aggregate limit** — the sum of transfers across the session is capped, so one
  large action cannot be split into many individually-allowed small ones.

Scenario B in the demo shows the last two: a write before any read is denied, and
two £9,000 transfers that each pass the single-call cap are stopped once their sum
crosses the session cap.

## This is a teaching model, not a policy engine

The file is ~120 lines of stdlib Python with hard-coded rules so you can feel the
difference. It is provider-neutral: no vendor, no MCP transport, no framework.

The production-grade version of this exact idea is **AWS Dogwood**, an open-source
(Apache 2.0) temporal extension of the **Cedar** policy language, released Aug 2026
and built on Metric First-Order Temporal Logic. It is backward-compatible with
Cedar (every valid Cedar policy is a valid Dogwood policy) and expresses these
patterns as real policies rather than Python `if` statements. If you want to ship
sequence-aware authorisation, use that, not this.
- AWS Open Source Blog: https://aws.amazon.com/blogs/opensource/introducing-dogwood-runtime-verification-for-ai-agents/

## What's still off

The rules here are illustrative and hard-coded; a real deployment writes them as
policy, versioned and reviewed, not baked into the guard. Session state has to be
tracked reliably for any of this to hold, and a temporal engine is only as good as
the trace it sees, if a tool call bypasses the mediator, it is invisible to the
policy. And sequence-aware authorisation raises the ceiling on what you can catch;
it does not remove the need for the point-in-time checks underneath. It is a
superset, never a substitute.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
