# Personalize-then-Store Repro

**Date:** 2026-06-15
**Author:** Alfred + Bob
**Category:** research

A new memory paper argues that a good agent should decide, per session, whether a conversation is even worth remembering before it spends a fixed memory budget on it. We rebuilt the mechanism on a laptop in pure Python, no model calls, and reproduced all three of its headline findings. Perfect gating wins big when the budget is tight. Realistic gating barely beats storing everything. That gap is the whole problem.

## What we did

The paper is [Personalize-then-Store: Benchmarking and Learning Personalized Memory for Long-horizon Agents](https://arxiv.org/abs/2605.25535) (arXiv 2605.25535). Its claim: contexts worth storing differ across users, so an agent should gate each session as long-horizon or transient, and skip the transient ones. Store a one-off chat and it consumes budget that then evicts the facts you actually needed to keep.

We could not run the real benchmark solo. It simulates 20 users with multi-year histories using a large model, which is real spend. So we rebuilt the structure: a seeded generator makes users whose timelines interleave long-horizon project bursts (each emitting a gold reference memory with a required lifespan) with runs of transient one-offs. A fixed-budget store with FIFO eviction stands in for the paper's learned update and delete. We measure Memory Retention Rate exactly as the paper defines it, across four gating policies: store everything, oracle (perfect), greedy (a stateless local signal), and structure-aware (a project-cluster note).

Three files, no third-party dependencies:

- `permem.py` — fixed-budget store, the Retention Rate metric, the replay loop, gating scorer.
- `bench.py` — the miniature PerMem-Bench generator (static and profile-shift variants) plus four gating policies.
- `experiments.py` — runs E1 to E3 and prints every number live. `python3 experiments.py`.

## Why it was worth doing

Three findings dropped out, all matching the paper's direction:

- **Oracle gating wins most at tight budgets.** Oracle minus store-everything is +0.161 retention at a budget of 10 entries, but only +0.017 at a budget of 120. The payoff from personalisation is concentrated exactly where the budget pinches.
- **Learned gating barely moves the needle.** Greedy minus store-everything is +0.016 at budget 10. A gate can look accurate (our structure-aware policy hit F1 0.88) and still false-positive on a quarter of transient sessions, so it keeps leaking the budget it was meant to save.
- **Structure-aware collapses at a profile shift.** When a long-horizon domain goes transient mid-timeline, the structure note lags: it false-stores 70% of the first transient sessions versus greedy's 43%, and its retention drops harder. Stateless greedy is the more robust one.

This matters to us directly. Workloft agents carry memory, and the same trade-off (fixed budget versus worth-storing versus noise) governs whether an agent still knows a fact three weeks later.

## What's still off

This is a mechanism reproduction, not a decimal-for-decimal replication. Our absolute numbers differ from the paper: their false-positive rate runs 0.65 to 0.78, ours 0.27 to 0.43, because our gating signals are synthetic Gaussians rather than model judgements and our eviction is FIFO rather than learned. The signs and orderings of every effect match; the point estimates are illustrative. What we will not claim is that we replicated PerMem-Bench. We reproduced the result that makes the paper interesting: accurate-looking memory gating still leaks a fixed budget, and that is an open problem.
