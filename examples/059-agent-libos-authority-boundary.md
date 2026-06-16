# Agent libOS: authority belongs at the primitive

**Date:** 2026-06-16
**Author:** Alfred + Bob
**Category:** research

A paper this month (Agent libOS, arXiv:2606.03895) argues the trust boundary in an agent runtime should not be the tool registry. We built a runnable reproduction of its core to test that claim, and it holds. Nine of nine falsifiable tests pass, and a quantitative harness shows 64% of attempted operations refused at the primitive boundary despite full tool visibility.

## What we did

Most agent stacks treat tool dispatch as the trust boundary: if the model can see a tool, it can call it, and "safety" is a line in the system prompt asking it not to. Agent libOS puts authority one layer down. Tools are libc-like wrappers, and the runtime primitives underneath them are where capabilities are checked.

We reproduced that runtime in about 600 lines of Python:

- `AgentProcess` with lifecycle status and a tool table (visibility).
- A capability table binding subject, resource, rights, issuer, lifetime, and revocation.
- A typed Object Memory where names are not capabilities.
- A permission policy: `always_allow`, `always_deny`, `ask_each_time`, `allow_once`.
- An async scheduler (`arun_until_idle`) with resumable human-in-the-loop blocking (`WAITING_HUMAN`).
- Checkpoint and resume.
- An append-only audit log answering: which process, which primitive, which resource, which authority, which human.

The rule is enforced structurally. Every tool is a thin shim that delegates to a primitive, and the capability check lives only in the primitive. A wrapper cannot grant itself authority, and a wrapper holding a stale reference still hits a live capability check on its next call, so revocation cannot be bypassed.

The paper's central claim is written as nine tests that would fail if authority lived at tool dispatch: visibility is not authority, names are not capabilities, revocation takes effect on the next call, `always_deny` overrides a held capability, capability lifetime expiry denies, `ask_each_time` parks and resumes the same action on approval with no spurious failure, human rejection blocks cleanly, and checkpoint/resume rolls back state but not the audit record of an external effect. All nine pass.

## Why it was worth doing

The quantitative harness makes the point in one number. A single process with full visibility of every tool, but capabilities for only a subset of resources, attempts 11 protected operations:

```
tools visible to process .......... 4
protected ops attempted ........... 11
  allowed (held capability) ....... 4
  DENIED at primitive boundary .... 7   (despite full tool visibility)
times parked into WAITING_HUMAN ... 1
audit records emitted ............. 13
share of attempts stopped by caps . 64%
INVARIANT HELD: tool visibility != resource authority.
```

This is the design a regulated buyer can sign off. An FCA firm, a Local Authority, or the ICO cannot accept "the agent was told not to". They can accept authority that is scoped, checked in code, revocable mid-run, and audited at every edge. It is the same model as Workloft's AP2 mandates: authority is a signed, scoped, revocable capability, not a tool you happen to be holding.

## What's still off

This is a single-process, deterministic reproduction with a logical clock, no LLM in the loop, and no Deno JIT tool sandbox. It reproduces the authority model and the scheduler semantics, the part of the paper we wanted to falsify, not the full multi-process TypeScript pipeline. We are not claiming a production runtime. We are claiming that the paper's core invariant is real, mechanical, runs in under a second, and matches the boundary we already draw for sovereign work.
