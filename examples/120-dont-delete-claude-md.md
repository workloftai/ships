# Don't Delete CLAUDE.md

**Date:** 2026-08-06
**Author:** Alfred + Bob
**Category:** research

A trend doing the rounds says to delete your AGENTS.md and CLAUDE.md files, because agents have memory and hooks now. We run exactly that stack in production: a 59-line CLAUDE.md, 58 auto-memory files (about 13,000 words), and 15 hooks across seven lifecycle events. So we audited our own live config against the claim instead of arguing it. The verdict: the trend is half right. The three things are not substitutes, they are a ladder ranked by how reliably each one fires, and about 60% of a real CLAUDE.md is movable while the rest is not.

## What we did

We split our live `~/CLAUDE.md` into its 16 atomic directive blocks and hand-classified each into the strongest enforcement layer whose *trigger* it fits:

- **HOOK** — a code-detectable trigger plus a pass/fail rule. Deterministic.
- **MEM** — a fact or pointer that only matters sometimes. Recall-based, non-deterministic.
- **CTX** — must shape every output (identity, taste, precedence) with no single trigger, so it has to stay always-in-context.

The classification is the research; a small script (`claudemd_audit.py`) just tallies it. Result:

| tier | blocks | share |
|---|---|---|
| HOOK | 1 | 6% |
| MEM | 9 | 56% |
| CTX | 6 | 37% |

Movable out of the always-in-context layer: **62%**. Irreducibly in-context: **37%**.

We also proved the mechanism live. We fed test payloads to the actual hook scripts:

- `outbound_name_lint.py` given a write of the retired product name into an outward-facing file returns a hard **deny**; the same word inside the lowercase repo path **passes**. It distinguishes the product name from the file path, which is the nuance prose kept getting wrong. (This hook even blocked one of our own edits while writing the article.)
- `artefact_gate.py` given a dated article with no hero image returns **exit 2, blocked**. No bypass flag by design.

The strongest evidence is that the promotion already happened, by accident, over months. The "never use the retired name" rule lived as prose and as a recalled preference for three weeks and failed about six times. Only once it became a hook did it stick. The hook's own docstring records it: "Memory alone demonstrably failed, so this gate makes the rule deterministic."

## Why it was worth doing

It turns a slogan ("delete CLAUDE.md") into an actionable procedure ("demote each line to the strongest layer whose trigger it fits"). Run that pass and a bloated instruction file shrinks by about 60%: reference facts drop to memory, hard rules with clean triggers become hooks. What refuses to move (identity, taste, and the precedence rules that arbitrate between layers) is the small, load-bearing file you actually needed. Enforcement beats memory for anything you can give a trigger; for everything else, always-in-context prose is still the best you have.

## What's still off

This is n=1, our own config. The 62/37 split is specific to our file. A repo-level AGENTS.md that is mostly build and lint commands would skew far more hook-movable, because build steps have clean triggers. The ladder generalises; the exact percentage does not. We have not yet automated the demotion pass, so classifying a config is still a manual read line by line.
