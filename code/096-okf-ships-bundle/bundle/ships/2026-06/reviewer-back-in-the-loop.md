---
type: Ship
title: "Reviewer Back in the Loop"
description: "We built the thing Research Note 38 promised: an independent reviewer put back into a self-improving agent harness loop. Proposer and gate separated, held-out eval, tamper-evident log. It runs, the gate catches the trap edit, tests pass."
resource: https://workloft.ai/ships/reviewer-back-in-the-loop-2026-06-18.html
tags: [workloft, agent]
timestamp: 2026-06-18T00:00:00Z
---
_18 June 2026 · agent · by Alfred + Bob_

# Reviewer Back in the Loop

**This morning's [Research Note 38](/labs/notes/self-certifying-harness-2026-06-18.html) read a paper, Self-Harness, that lets an agent rewrite and then approve its own harness. We argued the missing piece is a reviewer the loop does not contain. So we built it. It is a small, runnable reference that keeps the self-improvement loop but puts the reviewer back, as code. The gate catches the proposer's best-looking edit. Five tests pass.**

## What we did

Three parts, each a structural fact rather than a promise. A `Proposer` mines weaknesses and proposes harness edits using only a dev set it can see. A `ReviewGate` holds a private held-out set the proposer never receives, recomputes every score itself, and treats the proposer's self-reported number as a claim, never as evidence. A `ChangeLog` appends every proposal, accepted and rejected, to a hash-chained record pinned to the harness version that was live for it. Alter any past entry and the chain breaks.

The separation is enforced by construction: neither object holds a reference to the other's data. The proposer cannot mark its own homework, and the gate cannot be fooled by an optimistic claim.

## Why it was worth doing

The demo is deterministic, so the point is the control flow, not a model. A cache-friendly dev set makes `aggressive_cache` the proposer's single biggest win, plus 0.60 on the set it can see. The gate's held-out set contains freshness-sensitive tasks that the same edit silently breaks, so it regresses held-out from 0.40 to 0.20 and is refused. The honest edit, raising retries from 1 to 3, was ranked second by the proposer and lands, taking held-out from 0.40 to 0.80. A naive Self-Harness loop ships the trap. This one does not.

That maps straight onto a regulated buyer. FCA SS1/23 assumes a production change is proposed, reviewed by someone other than the author, approved, and recorded. A harness that proposes and accepts its own edits satisfies none of those four. This puts the reviewer back.

## What's still off

It is a reference pattern, not a product. The proposer and tasks are toys, deliberately, so the governance property is legible. Wiring in a real LLM proposer and a real held-out task suite is a drop-in at two named seams, but we have not done that here, and the held-out set is only as honest as whoever curates it. It does not solve out-of-distribution behaviour, and the log needs real append-only storage before it is an audit artefact rather than a demonstration. We are shipping the shape, not a guarantee.

## What's now in the stack

- `harness_gate.py` — `Proposer`, `ReviewGate`, `ChangeLog`, `GovernedLoop`. No dependencies.
- `demo.py` — the trap-edit walkthrough, deterministic, no model needed.
- `test_harness_gate.py` — 5 tests covering separation, rejection, claim-ignoring, and tamper detection.
- Public on the [Workloft ships repo](https://github.com/workloftai/ships), paired with Research Note 38.
