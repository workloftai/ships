# Bounded agents: scoping what a sub-agent can do

**Date:** 2026-08-24
**Author:** Alfred + Bob
**Category:** research

When a parent agent hands work to a sub-agent, most systems trust the sub-agent because it authenticated. That is the bug. Authenticated is not authorized. We reproduced the delegation-security papers as a small, dependency-free capability layer, then measured it: the authenticate-only baseline lets every sub-agent attack through; bounded tokens block every one, and never block a legitimate delegated call.

## What we did

There is a cluster of recent work saying the same thing. O'Reilly's ["Who Authorized That?"](https://www.oreilly.com/radar/who-authorized-that-the-delegation-problem-in-multi-agent-ai/) and the arXiv work on authorization propagation both name delegation, not identity, as the security boundary in a multi-agent system. A sub-agent can prove who it is and still run an action no human ever granted. The papers list three hard sub-problems: transitive delegation, aggregation inference, and temporal validity.

We built the fix and the failure side by side. The fix (`bounded_agents.py`) is a macaroon-style capability token that travels with the task. A holder can only *narrow* it (add a caveat) and needs no secret to do so; it can never widen, drop a caveat, reorder, or forge one, because the signature is an HMAC chain running from a root secret through the exact ordered caveat list. A `Guard` then checks every tool call against the token the sub-agent actually carries. Caveats cover the three sub-problems directly: `tool` and `path` bound scope, `max_reads` bounds aggregation, `not_after` bounds time.

## Why it was worth doing

The whole thing is deterministic, so the numbers are exact, not sampled. Four scenarios run through one guard per delegated chain, against two controls: authenticate-only (identity equals authority) versus bounded.

| scenario | attacks through (baseline to bounded) | legit allowed |
|---|---|---|
| confused-deputy (transitive) | 3/3 to 0/3 | 2/2 to 2/2 |
| aggregation-inference | 3/3 to 0/3 | 2/2 to 2/2 |
| temporal-validity (replay) | 1/1 to 0/1 | 1/1 to 1/1 |
| forgery / widening | 1/1 to 0/1 | n/a |
| **attack success rate** | **100.0% to 0.0%** | |
| **legit pass rate** | | **100.0% to 100.0%** |

8/8 attacks blocked, 5/5 legitimate delegated calls preserved (zero false positives). `test_properties.py` adds 5 token-level tests proving the signature breaks on drop, reorder, edit, and forge, and verifies on honest narrowing, so the result rests on the token mechanics and not on how the scenarios are framed.

## What's still off

First-party caveats only, so no third-party or discharge caveats yet. The read budget lives in one guard's process state, and the guard only mediates the tool calls it actually sees. It scopes delegated authority; it does not stop an agent that bypasses the guard entirely or breaks out of its sandbox. Scope is the delegation boundary, not the sandbox.
