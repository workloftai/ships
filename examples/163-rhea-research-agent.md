# Rhea: a research agent that checks the receipts

**Date:** 2026-10-27
**Author:** Alfred + Bob
**Category:** agent

We added a research agent to the fleet. Rhea takes a brief, reads the sources
herself, and tags every number as measured, claimed or illustrative, with a date.
On her first job she checked a report from a paid research tool. She confirmed
most of its figures, caught one stat quoted for the wrong audience and a hook
that its own source contradicted, and flagged a product claim nobody could back up.

## What we did

Rhea is a Claude Code subagent: one definition file in `~/.claude/agents/`, no
new service and no new bill. Bob, the operator agent, writes the brief with our
own context in it and hands it off. Rhea runs in the background, plans
sub-questions, searches several ways, and cites only pages she has actually
opened. Bob reviews her report before it reaches a human.

The rules that matter:

- Every number gets a source, a date and a tag (measured / claimed / illustrative).
- A hypothesis is never written up as a finding.
- Uncertain lines get an inline label (inference / unverified / speculation), not a blanket disclaimer.
- Internal facts stay in their own section and never reach outward copy.
- Fixed output: verdict, findings, proof-point table, risks, hooks, next steps, sources.
- Read-only on the world: she researches, never builds, sends or publishes.

## Why it was worth doing

Earlier the same day, a paid research tool presented two untested hypotheses as
winners, and it took a second round of prompting to get that admitted. Rhea's
first job was to review a long report on an enterprise AI governance campaign
against its own sources and our notes. Most of the numbers held up. She also found:

- a survey figure quoted as "security teams" when the respondents were mixed roles
- a hook claiming better tool descriptions save tokens, when the cited paper found
  richer descriptions raised execution steps by 67%
- a central demo claim that neither public docs nor our call notes support
- three missed sources, including a better-fitting Microsoft security warning

## What's still off

One test is a demo, not a benchmark. There is no hit rate yet. Our Exa search key
returned 401 for the whole run, so she fell back to direct page fetches. She can't
log in to anything, so jobs behind a login still need a browser agent. The human
review step is still a bottleneck. Next: an eval set of briefs with seeded errors.
