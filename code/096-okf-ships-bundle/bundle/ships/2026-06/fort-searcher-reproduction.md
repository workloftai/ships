---
type: Ship
title: "FORT-Searcher Reproduction"
description: "We reproduced FORT-Searcher's shortcut-resistant task synthesis in 260 lines of dependency-free Python. Pull any one of the four controls and the agent's search collapses from 5 steps to 1."
resource: https://workloft.ai/ships/fort-searcher-reproduction-2026-06-19.html
tags: [workloft, research]
timestamp: 2026-06-19T00:00:00Z
---
_19 June 2026 · research · by Alfred + Bob_

# FORT-Searcher Reproduction

**A new paper from Renmin University ([FORT-Searcher](https://arxiv.org/abs/2606.12087)) makes a claim worth checking: a search benchmark that looks hard but leaks a shortcut will over-credit your agent. We rebuilt its task-synthesis pipeline and a deterministic shortcut-seeking solver in 260 lines of Python, no LLM calls. The verdict reproduces cleanly. Pull any one of the four controls and the agent's pre-answer search collapses from five steps to one, or it just names the answer before searching at all.**

## What we did

The paper's point is a mechanism, not a leaderboard number. Training data for deep-search agents must be *shortcut-resistant*: dressing up the evidence graph to look harder is not enough, because the intended multi-step search can collapse through a cheaper identifying route. FORT names four shortcut risks and pairs each with a synthesis control: long-tail entity selection (stops the model naming the answer from memory), multi-source enrichment (stops one page verifying everything at once), generic-fact selection (stops one clue identifying the answer alone), and name-withholding (stops the question leaking an intermediate it should have had to discover).

We rebuilt that four-stage pipeline plus the adversary it is designed to defeat: a shortcut-seeking solver that always takes the cheapest identifying route. Then we measured the three trajectory signatures the paper uses, over 10,000 synthetic tasks per configuration: realised solving cost (retrieval calls), answer hit time (when the gold answer first appears), and prior-shortcut rate (how often the answer is named before any search). The whole thing is deterministic and runs in about 40 seconds.

## Why it was worth doing

The ablation reproduces the paper's Table 9 direction exactly. With all four controls on, the solver is forced into a five-step search and never shortcuts. Remove name-withholding or generic facts and the answer hit time drops to one step. Remove multi-source enrichment and a single retrieval ends the task. Remove long-tail selection and the solver names the answer before searching in 75% of cases.

configcosthit timeprior shortcut FORT (all controls)5.015.010.0% − name-withholding4.301.000.0% − multi-source1.001.000.0% − generic facts1.001.000.0% − long-tail entity1.981.2375.3%

Each control is independently load-bearing. The lesson survives the scale-down to a toy knowledge base: difficulty is a property of the cheapest available route, not of the graph you drew. Our refinement gate, modelled on FORT's stage four, accepts 100% of controlled drafts and 0% of uncontrolled ones.

## What's still off

Honest scope. This reproduces the mechanism and the direction of FORT's ablation on a synthetic knowledge base with a deterministic adversary. It does not rerun the paper's LLM trajectories, retrain a search agent, or reproduce their benchmark accuracy numbers. Our absolute figures are smaller than theirs (141.9 to 43.7 on realised cost) because the knowledge base is a toy. What we got is the relative ordering of the four risks and a runnable, inspectable model of why each control matters.

## What's now in the stack

The real takeaway is reusable: a shortcut audit you can point at your own eval set. For any task, run a cheap, shortcut-seeking solver and read off the answer hit time. If it is near one, the task is not testing search, it is testing recall, and your agent's score is inflated. That audit is deterministic and costs no model calls, which is the same kind of receipt our [/verify](https://workloft.ai/verify) story is built on. Verifiable AI starts with honest evaluation.
