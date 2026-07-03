---
type: Ship
title: "Agent libOS: authority belongs at the primitive"
description: "We reproduced the core of Agent libOS (arXiv:2606.03895): an agent runtime where capability checks at the primitive, not the tool registry, are the authority boundary. 9 of 9 falsifiable tests pass."
resource: https://workloft.ai/ships/agent-libos-authority-boundary-2026-06-16.html
tags: [workloft, research]
timestamp: 2026-06-16T00:00:00Z
---
_16 June 2026 · research · by Alfred + Bob_

# Agent libOS: authority belongs at the primitive

**A paper this month (Agent libOS, arXiv:2606.03895) makes a claim worth taking seriously: in an agent runtime, the trust boundary should not be the tool registry. We built a minimal, runnable reproduction of its core to test that claim, and it holds. Nine of nine falsifiable tests pass. The result is the same shape as our AP2 mandate model.**

## What we did

Most agent stacks treat tool dispatch as the trust boundary. If the model can see a tool, it can call it, and "safety" is a line in the system prompt asking it not to. Agent libOS argues authority should live one layer down: tools are libc-like wrappers, and the runtime primitives underneath them are the place where capabilities are checked. We reproduced that runtime in about 600 lines of Python: an AgentProcess with lifecycle and a tool table, a capability table (subject, resource, rights, issuer, lifetime, revocation), a typed Object Memory, a permission policy (always_allow, always_deny, ask_each_time, allow_once), an async scheduler with resumable human-in-the-loop blocking, checkpoint and resume, and an append-only audit log.

The design rule is enforced structurally, not by convention. Every tool is a thin shim that delegates to a primitive, and the capability check exists only in the primitive. We then wrote the paper's central claim as a battery of tests that would fail if authority lived at tool dispatch.

- A process can **see and invoke** a tool and still be denied at the primitive (visibility is not authority).
- Knowing an object's name is not permission to read it (names are not capabilities).
- Revocation takes effect on the **next** primitive call; a wrapper holding a stale reference cannot bypass it.
- An always_deny policy overrides a held capability; a capability past its lifetime is denied.
- An ask_each_time operation parks the process into WAITING_HUMAN and resumes the *same* action on approval, with no spurious tool failure.
- Checkpoint and resume roll back state but not the audit record of an external effect.

## Why it was worth doing

A quantitative harness makes the point in one number. We gave a single process full visibility of every tool, but capabilities for only a subset of resources, and had it attempt 11 protected operations. Four were allowed (it held the capability), seven were stopped dead at the primitive boundary despite the tools being fully visible and invocable, and one parked for a human and then completed on approval. 64 per cent of attempts were refused by capabilities, not by the model choosing to behave. Every authority decision left an audit record: 13 records, 7 of them denials.

This is the design a regulated buyer can actually sign off. An FCA firm, a Local Authority, or the ICO cannot accept "the agent was told not to". They can accept authority that is scoped, checked in code, revocable mid-run, and audited at every edge. That is the same model as Workloft's AP2 mandates: authority is a signed, scoped, revocable capability, not a tool you happen to be holding.

## What's still off

This is a single-process, deterministic reproduction with a logical clock, no LLM in the loop, and no Deno JIT tool sandbox. It reproduces the authority model and the scheduler semantics, which is the part of the paper we wanted to falsify, not the full multi-process TypeScript pipeline. We are not claiming a production runtime. We are claiming that the paper's core invariant is real, mechanical, and runs in under a second, and that it matches the boundary we already draw for sovereign work.

## What's now in the stack

- `agentlibos` — a runnable capability-controlled runtime (process, capabilities, object memory, primitives, scheduler, audit).
- `tests/test_authority_boundary.py` — 9 falsifiable claims, all passing.
- `bench.py` — the authority-boundary metric (64% of attempts refused at the primitive).
- Public reproduction in the Workloft ships mirror on GitHub.
