---
stage: plan
status: draft
parent: spec.md
parent_sha256:
---

# Plan: <short title>

<!--
parent_sha256 is stamped by `chain_check.py --seal` when the engineer accepts
the plan. If spec.md changes after that, chain_check fails and the plan is stale.
This file should be complete enough to hand to a fresh agent with no other context.
-->

## Files that change
The exact paths, and one line on what changes in each.

## Order of work
The steps, in sequence. What has to land before what.

## Risks
What could break, and the blast radius.

## Proof
How you will know it worked. Tests, lint, the command to run, the expected output.
