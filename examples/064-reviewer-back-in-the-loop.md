# Reviewer Back in the Loop

**Date:** 2026-06-18
**Author:** Alfred + Bob
**Category:** agent

This morning's Research Note 38 read a paper, Self-Harness (arXiv:2606.09498), that lets an agent rewrite and then approve its own harness. We argued the missing piece is a reviewer the loop does not contain. So we built it: a small, runnable reference that keeps the self-improvement loop but puts the reviewer back, as code. The gate catches the proposer's best-looking edit. Five tests pass.

## What we did

Three parts, each a structural fact rather than a promise.

- A `Proposer` mines weaknesses and proposes harness edits using only a dev set it can see.
- A `ReviewGate` holds a private held-out set the proposer never receives, recomputes every score itself, and treats the proposer's self-reported number as a claim, never as evidence. Acceptance requires no regression on the held-out set, plus clearing an absolute floor.
- A `ChangeLog` appends every proposal, accepted and rejected, to a hash-chained record pinned to the harness version that was live for it. Each entry's hash covers the previous one, so altering any past entry breaks the chain. `verify()` walks it.

The separation is enforced by construction: neither object holds a reference to the other's data. The proposer cannot mark its own homework, and the gate cannot be fooled by an optimistic claim.

The deterministic demo makes the failure mode concrete. A cache-friendly dev set makes `aggressive_cache` the proposer's single biggest win (plus 0.60 on the set it can see). The gate's held-out set contains freshness-sensitive tasks the same edit silently breaks, so it regresses held-out from 0.40 to 0.20 and is refused. The honest edit, raising retries from 1 to 3, was ranked second by the proposer and lands, taking held-out from 0.40 to 0.80. A naive Self-Harness loop ships the trap. This one does not.

Files: `harness_gate.py` (Proposer, ReviewGate, ChangeLog, GovernedLoop, no dependencies), `demo.py`, `test_harness_gate.py` (5 tests), `README.md`.

## Why it was worth doing

The paper's validation step, "accepts candidate edits only after regression testing", is a producer grading its own work when the proposer also picks the regression set. That maps straight onto a regulated buyer. FCA SS1/23 assumes a production change is proposed, reviewed by someone other than the author, approved, and recorded. A harness that proposes and accepts its own edits satisfies none of those four. This puts the reviewer back, and turns "the harness changed itself" into something you can evidence rather than screenshot.

## What's still off

It is a reference pattern, not a product. The proposer and tasks are toys, deliberately, so the governance property is legible. Wiring in a real LLM proposer and a real held-out task suite is a drop-in at two named seams, but we have not done that here, and the held-out set is only as honest as whoever curates it. It does not solve out-of-distribution behaviour, and the log needs real append-only storage before it is an audit artefact rather than a demonstration. We are shipping the shape, not a guarantee.
