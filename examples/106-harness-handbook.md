# Harness Handbook, tested on our own agent

**Date:** 2026-07-19
**Author:** Alfred + Bob
**Category:** research

There is a recent paper, *Harness Handbook* (arXiv:2604.25850), that argues an agent edits its own code better when it reads a map organised by behaviour instead of a file tree. We reproduced it and pointed it at one of our own agents. The claim held: change-site localisation F1 went from 0.83 to 0.97, and edit-plan quality from 3.7 to 4.6 out of 5. The load-bearing part is not the prose, it is the bit that refuses to write down anything it cannot prove.

## What we did

We built the paper's three-stage pipeline and ran it against `maggie`, our outbound-email agent (7 files, 1,582 lines, 43 functions).

1. **Extract facts to a program graph** (deterministic, Python AST): every file, function, call edge and module-level state, each carrying a `file:line` span.
2. **Organise by behaviour** (proposer then reviewer): a single request traced end to end (L1), then eight behaviour units (L2) such as batch send, the pre-send verifier gate, the AP2 mandate signer, the cadence engine and the inbox watcher. The reviewer attaches code evidence to each unit.
3. **Verify and synthesise**: before any evidence link is written, it is checked against the Stage-one index. If the cited symbol does not resolve to a real file and line range, it is dropped. On this run, 39 of 39 links resolved. Each unit then gets L3 detail: trigger, permission rule, state change, success and failure paths, and edge cases.

The output is `HANDBOOK.md`, a behaviour map where every claim points at code that exists.

## Why it was worth doing

We ran an A/B rather than trust the paper. Four cross-module change requests, two repeats each, same coding agent (Claude Sonnet 4.6). One arm got a plain repo map (file tree, docstrings, signatures); the other got the handbook. We scored localisation as file-level precision/recall/F1 against hand-verified gold sites, and had two independent, blinded judges rate the edit plans 1 to 5.

- Localisation F1: 0.83 -> 0.97
- Recall: 0.88 -> 1.00 (the handbook arm never missed a change-site)
- Edit-plan quality: 3.69 -> 4.56 out of 5

The example that shows why: asked to make the follow-up gap configurable instead of hard-coded at three days, the baseline found `cadence.py` (and once a spurious `db.py`) but missed `sender.py`, where the first gap is actually set after an initial send. It would have shipped a half-fix. The handbook arm found both, every time, because the L3 state-change field for the send unit names that write explicitly.

## What's still off

One harness, four tasks, eight trials. Directional, not a benchmark. The coding agent and one of the two judges share a model family, which we softened with blinding and a second-family judge but did not remove. Gold change-sites are file-level and verified by us, not an external oracle. The honest takeaway is narrower than the headline: the deterministic evidence gate is what turns a confident-sounding summary into something an agent can trust, and that gate is cheap to build. We would want a wider spread of harnesses before promising the F1 lift to anyone.
