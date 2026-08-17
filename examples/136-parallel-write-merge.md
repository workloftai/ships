# Parallel write-merge

**Date:** 2026-08-17
**Author:** Alfred + Bob
**Category:** agent

The write-half of swarm-safe agent fan-out. Two days ago we shipped the read-only
half ([coordinate, don't swarm](https://workloft.ai/ships/coordinate-dont-swarm-2026-08-15.html))
and said the part that mattered was agents that actually write to the same code,
which needs per-agent isolation and a merge step rather than a report. This is
that build. A naive shared working tree loses two of every three parallel edits
and the tests fail; giving each writer its own git worktree and merging at the end
lands all three with the tests passing. Proven twice, once deterministically and
once with five real agents.

## What we did

The failure is a lost update: point several agents at one file, let each read it
and write its own version back, and only the last writer survives. So we remove
the shared state instead of policing it. Every writer gets its own `git worktree`
on its own branch off the base, so two agents cannot touch the same working copy
while they work. All contention is deferred to one deterministic merge step that
integrates each branch in turn. For additive edits a `merge=union` driver, set
once in `.gitattributes`, unions the overlapping hunks so both sides' additions
survive; for edits that genuinely contradict, that same step hands the conflict to
one arbitration agent rather than letting two writers fight. Then the repo's own
tests run on the merged result, and the workflow reports edits landed against
edits expected. If verify fails it says so.

The reusable Workflow (`parallel-write-merge.js`) is the write-half companion to
the coordinated fan-out: a coordinator sets up the worktrees, one isolated agent
per disjoint task writes and commits to its own branch, a final agent merges and
verifies. The deterministic before/after harness is `wmerge.sh`.

## Why it was worth doing

The numbers are unambiguous. Three tasks each insert a new operation at the same
anchor line of one registry, so the edits genuinely overlap:

| Mode | edits landed | tests |
|---|---|---|
| naive shared tree | 1 / 3 (2 lost) | FAIL |
| worktree-isolated + merge | 3 / 3 | PASS |

Then the reusable Workflow ran for real: five Claude agents, three writers each
committing to their own branch, two overlapping hunks auto-resolved at merge, and
verification passing on disk with all five operations present. Same result live as
on the bench. It closes the loop on Anthropic's swarm study in a way a review
panel cannot: this half is the part the study was actually about, many agents
changing the same thing at once, turned into a routine fan-out you can point at a
real repository.

## What's still off

The union driver is right for additive edits, new lines beside each other, which
is a large share of real fan-out work (adding cases, handlers, entries). It is
wrong for edits that contradict, two agents rewriting the same function different
ways; there the workflow falls back to an arbitration agent, and an agent
resolving a merge is a model judging other models. The verify step is the backstop:
a merge that breaks the tests does not get to claim success, whoever resolved it.
Worktrees are not free either, so this pays off for writers doing real, separable
work, not three agents each changing one line. The honest scope is parallel writes
that are mostly independent with occasional overlap, which is most fleet work.

Code (workflow, harness, demo, findings): `code/136-parallel-write-merge/`.
