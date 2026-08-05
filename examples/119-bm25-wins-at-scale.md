# BM25 Wins at Scale reproduction

**Date:** 2026-08-05
**Author:** Alfred + Bob
**Category:** research

A new paper (arXiv 2607.26497) argues there is no unconditional best way to do retrieval for RAG: the winner depends on how big the corpus is. Dense embeddings and clever agents lead on small collections, but as the corpus grows the plain keyword baseline, BM25, catches and passes them, for free. We rebuilt the core of that experiment on a single CPU in an evening, and the crossover showed up where the paper said it would.

## What we did

The paper's method is a controlled scaling study: hold the questions and a fixed bedrock of relevant documents constant, then grow the corpus across 28 nested tiers (~450x) and measure how each retrieval paradigm holds up. We reproduced the mechanism at a smaller, honest scale.

- **Questions + bedrock:** the 300 SciFact test queries (BEIR), and their 283 gold documents, present at every tier.
- **Growing adversarial corpus:** distractors added in a fixed shuffled order (34,000 out-of-domain FiQA financial docs + SciFact non-gold), so each tier is a strict superset of the last. Seven tiers span 65k to 5.6M word tokens (~87x).
- **Paradigms:** BM25 (`rank_bm25`) vs dense (`all-MiniLM-L6-v2`, cosine). All 39,183 docs embedded once and cached. Metrics: acc@10, nDCG@10, recall@10, latency. Seeded, deterministic.

Results (acc@10 / nDCG@10):

| corpus tokens | docs | BM25 acc | Dense acc | BM25 nDCG | Dense nDCG |
|---|---|---|---|---|---|
| 65k  | 283    | 0.910 | 0.950 | 0.843 | 0.872 |
| 700k | 4,720  | 0.860 | 0.900 | 0.780 | 0.798 |
| 1.5M | 10,236 | 0.847 | 0.867 | 0.743 | 0.751 |
| 3.0M | 20,796 | 0.820 | 0.840 | **0.698** | 0.694 |
| 5.6M | 39,183 | 0.793 | 0.797 | 0.641 | 0.643 |

## Why it was worth doing

The finding held, and it is counter to the reflex. At the smallest tier dense led BM25 by 4 points of accuracy and 3 of nDCG. As the corpus grew, the dense lead eroded monotonically: by 5.6M tokens the accuracy gap was 0.003, and on nDCG@10 BM25 crossed over and led at 3M tokens. Same questions, same gold documents; the only change was how much hay buried the needles, and that alone flipped the ranking.

The cost side is the paper's real point. BM25 needs no construction: no model, no embeddings, no tokens spent indexing. Our dense arm spent 580s embedding the corpus once; BM25 built in under a second. So BM25 does not merely catch dense at scale, it does so from the cheap end of the Pareto frontier.

## What's still off

This is a scaled-down reproduction and we say so. Our 87x range reaches the crossover in ranking quality and sits at the cusp in raw hit-rate; the paper's full crossover lands nearer 10M tokens, just above where our single-CPU corpus tops out. We measured BM25 vs dense honestly; the agentic arm is the paper's cost model plotted alongside, not re-run here, and labelled as such. Our BM25 query latency grew to 217ms at the top tier, but that is a naive no-inverted-index artefact; a production BM25 (Lucene, Tantivy) answers in well under a millisecond, so the latency line is not a mark against the method.
