# Parallel write-merge — the swarm-safe WRITE half

**Item:** 26f32356 — Wire Claude Code subagent forking + SendMessage into a Bob workflow.
Read-half shipped earlier as #137 (coordinate, don't swarm). This is the harder write-half.

## The problem (Anthropic swarm turf-war study)
When many agents mutate ONE shared working tree, they clobber each other: lost
updates, hidden edits, outright sabotage. Coordination-by-report (the read-half)
avoids it by never writing. But real fleet work needs writes.

## The pattern
1. **Isolation** — remove the shared state entirely. Every writer gets its OWN
   git worktree + branch. Two writers physically cannot touch the same working copy.
2. **One merge step** — contention is deferred to a SINGLE deterministic
   merge/arbitration point (never two agents fighting over the same lines). A
   `merge=union` .gitattributes driver auto-resolves overlapping additive hunks.
3. **Verify** — run the repo's tests on the merged result; report edits landed
   vs expected. If verify fails, say so — never claim success.

## Proof (deterministic, no agents)
Three tasks each insert a new op at the SAME anchor in one OPS registry → real
overlapping git hunks.

| Mode | edits landed | tests |
|---|---|---|
| naive shared tree | **1 / 3** (2 lost) | FAIL |
| worktree-isolated + merge | **3 / 3** | PASS |

Naive keeps only the last writer (classic lost-update). Isolated lands all three,
union-merge output not garbled.

## Proof (live, 5 real Claude agents via Workflow)
`~/.claude/workflows/parallel-write-merge.js`: setup → 3 isolated writers → merge+verify.
- 3/3 writers committed to their own branch (w/mul, w/div, w/pow).
- merge auto-resolved 2 overlapping hunks (union driver); 1 clean fast-forward.
- verify PASSED on disk: `PASS: all 5 ops present`. edits_landed 3/3.

## Artefacts
- `~/.claude/workflows/parallel-write-merge.js` — reusable named workflow.
- `~/loop-build/parallel-write-merge/wmerge.sh` — deterministic harness + before/after.
