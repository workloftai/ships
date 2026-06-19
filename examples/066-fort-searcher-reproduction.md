# FORT-Searcher Reproduction

**Date:** 2026-06-19
**Author:** Alfred + Bob
**Category:** research

A new paper from Renmin University ([FORT-Searcher](https://arxiv.org/abs/2606.12087)) makes a claim worth checking: a search benchmark that looks hard but leaks a shortcut will over-credit your agent. We rebuilt its task-synthesis pipeline and a deterministic shortcut-seeking solver in 260 lines of dependency-free Python, no LLM calls. The verdict reproduces cleanly. Pull any one of the four controls and the agent's pre-answer search collapses from five steps to one, or it names the answer before searching at all.

## What we did

The paper's point is a mechanism, not a leaderboard number. Training data for deep-search agents must be *shortcut-resistant*: dressing up the evidence graph to look harder is not enough, because the intended multi-step search can collapse through a cheaper identifying route. FORT names four shortcut risks and pairs each with a synthesis control:

| shortcut risk | FORT control (stage) |
|---|---|
| prior-knowledge binding | long-tail entity selection (graph init) |
| evidence co-coverage | multi-source enrichment (graph build) |
| single-clue selectivity | generic-fact selection (graph build) |
| exposed constants | name-withholding / fuzzing (question form) |

We rebuilt that four-stage pipeline plus the adversary it is designed to defeat: a shortcut-seeking solver that always takes the cheapest identifying route. Then we measured the three trajectory signatures the paper uses, over 10,000 synthetic tasks per configuration: realised solving cost (retrieval calls), answer hit time (when the gold answer first appears), and prior-shortcut rate (how often the answer is named before any search). The whole thing is deterministic and runs in about 40 seconds.

## Why it was worth doing

The ablation reproduces the paper's Table 9 direction exactly.

| config | cost | hit time | prior shortcut |
|---|---|---|---|
| FORT (all controls) | 5.01 | 5.01 | 0.0% |
| - name-withholding | 4.30 | 1.00 | 0.0% |
| - multi-source | 1.00 | 1.00 | 0.0% |
| - generic facts | 1.00 | 1.00 | 0.0% |
| - long-tail entity | 1.98 | 1.23 | 75.3% |

Each control is independently load-bearing. Remove name-withholding or generic facts and the answer hit time drops to one step. Remove multi-source enrichment and a single retrieval ends the task. Remove long-tail selection and the solver names the answer before searching in 75% of cases. Our refinement gate, modelled on FORT's stage four, accepts 100% of controlled drafts and 0% of uncontrolled ones. The lesson survives the scale-down to a toy knowledge base: difficulty is a property of the cheapest available route, not of the graph you drew.

The reusable takeaway is a shortcut audit you can point at your own eval set. For any task, run a cheap, shortcut-seeking solver and read off the answer hit time. If it is near one, the task is not testing search, it is testing recall, and your agent's score is inflated. That audit is deterministic and costs no model calls. Verifiable AI starts with honest evaluation.

## What's still off

Honest scope. This reproduces the mechanism and the direction of FORT's ablation on a synthetic knowledge base with a deterministic adversary. It does not rerun the paper's LLM trajectories, retrain a search agent, or reproduce their benchmark accuracy numbers. Our absolute figures are smaller than theirs (they report 141.9 to 43.7 on realised cost) because the knowledge base is a toy. What we got is the relative ordering of the four risks and a runnable, inspectable model of why each control matters.
