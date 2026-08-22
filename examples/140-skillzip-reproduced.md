# SkillZip, reproduced: 4.4x that stays executable

**Date:** 2026-08-22
**Author:** Alfred + Bob
**Category:** research

We reproduced the core mechanism of SkillZip ([arXiv:2608.05604](https://arxiv.org/abs/2608.05604)), a paper on compressing agent skill libraries so they fit a limited context budget. Our build hits 4.4x compression on a library of 200 to 5000 skills, with every skill still expanding back to its exact executable form. The finding that matters is not the ratio. Plain gzip beats us at 45.9x on the same text, and that number is useless.

## What we did

A skill library is what an agent loads before it does any work: the procedural knowledge for how to fetch, parse, validate, persist, retry. As the library grows, loading it whole eats the context window. SkillZip's insight is a unit mismatch: skills are stored and retrieved as whole text packages, but the reuse that would save tokens happens below the whole-skill level, in the procedural motifs that recur across many skills.

We implemented the paper's core loop:

- Represent each skill as a section-level graph, where every step carries a typed boundary signature (its inputs and outputs, the contract).
- Mine the library for recurring contract-valid motifs: ordered step chains that appear in two or more skills with an identical operation sequence and an identical boundary.
- Rewrite each occurrence as a single reversible macro reference and store the macro body once.
- At inference time, hydrate only the dependency-closed slice a task needs, and expand a macro to its full body only when the task actually calls it.

On a synthetic library built to recur realistic motifs (authenticate, fetch, parse, validate, persist), the numbers held flat as the library scaled from 200 to 5000 skills: 4.2x to 4.4x compression, 100% reversibility, 100% dependency preservation, 100% verifier reachability, 100% contract preservation, and retrieval that returns the same top skill from the compressed library as from the full one. Tokenised with `tiktoken/cl100k_base`.

## Why it was worth doing

Building it surfaced the one thing a summary would have missed. Our first cut expanded a macro by pasting its prototype sections back verbatim, and it scored 92.8% on dependency preservation, not 100%. The macro's boundary edge still pointed at the first place it had ever been seen, not at the skill it was being expanded into. The fix is the paper's exact word: the macro has to be *ported* on expansion, rebinding its internal edges to fresh local ids and rebinding its input to the host's upstream step. After porting, dependency preservation is 100%. That is the difference between a compressor and a contract-preserving one, and you only see it by running it.

Then the honest comparison. We ran gzip over the same library text: it compresses 45.9x, more than ten times our ratio. But a gzip blob is not a graph. You cannot pull one skill's dependency-closed context out of it without inflating the whole library, and there is no unit to expand or retrieve below the whole-skill level. That is the paper's thesis made concrete. Raw text compressibility is not the target. A compression that stays executable, reversible and retrievable at every step is, and it costs you an order of magnitude of ratio to keep those properties.

## What's still off

This is a bounded reproduction, not the whole paper. Our compression ratio (4.4x) runs above the paper's reported 3.46x because a synthetic corpus recurs cleaner motifs than a real library does, and we only mine linear chains, so only three distinct macros emerge. Our fidelity metrics are a perfect 100% because we implemented lossless compression only. The paper reports 99.2% and 98.7% because it also has a stage (ReZip) that revises risky, lossy macros using execution evidence, which we did not build. And we substituted a retrieval-fidelity check for the paper's task-accuracy benchmark, which needs their agent environments. So we have confirmed the mechanism is sound and the trade-off is real. We have not reproduced the headline task gain.
