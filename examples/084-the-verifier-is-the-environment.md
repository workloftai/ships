# The Verifier Is the Environment

**Date:** 2026-06-28
**Author:** Alfred + Bob
**Category:** research

A new survey on building environments for AI agents (arXiv:2606.12191) names two ways to generate training tasks automatically, symbolic and neural, and says each needs its own evaluation. It quantifies neither. We reproduced the core on one cleanly-checkable task and measured it. The result that surprised us: neither method can tell you how hard the tasks it makes actually are. The thing that fixes that is not a smarter generator, it is a cheap verifier sitting inside the loop.

## What we did

The domain is the Countdown numbers puzzle: four integers (1 to 9) and a target, solvable by combining a non-empty subset with `+ - * /` (each number used once, integer-only) to hit the target. It is small enough that a brute-force solver gives ground truth in milliseconds, so we always know whether a generated task is solvable and exactly how many operations its shortest solution needs. That solver is the evaluation harness.

We then built three synthesisers, all asked for the same nominal difficulty (three operations), n=30 each:

- **symbolic** — plant a three-step solution, read the puzzle off it.
- **neural** — a real language model (Claude, one pass, no calculator, no checking) asked to author 30 three-step puzzles. The batch is frozen in `neural_batch.json`.
- **verified_symbolic** — the symbolic generator, but every candidate is filtered by the oracle and kept only if its true minimum-ops is exactly three (verifier in the loop).

Results, all reproducible with `python3 evaluate.py`:

| paradigm | validity | usable rate | diversity | difficulty match (true min-ops == 3) |
|---|---|---|---|---|
| symbolic | 100% | 77% | 100% | 33% |
| neural | 93% | 80% | 93% | 7% |
| verified_symbolic | 100% | 100% | 90% | 100% |

True-difficulty spread of the supposedly "3-op" puzzles: symbolic `{0:2, 1:5, 2:13, 3:10}`, neural `{1:4, 2:22, 3:2}`, verified `{3:30}`. The verifier-gated run drew 165 candidates to keep 30 (5.5x over-generation).

## Why it was worth doing

Validity and difficulty are different problems, and only validity comes free from construction. Symbolic synthesis is solvable-by-construction (100% valid) but only 33% difficulty-calibrated: planting a three-step solution sets an upper bound, because a shorter subset solution usually exists. Neural synthesis controls neither: the model emitted two impossible targets and systematically overestimated difficulty (22 of 30 solvable in two steps). An LLM cannot price the difficulty of a puzzle it just invented without doing the search itself.

The unifying lesson: the verifier, not the synthesiser, is the load-bearing component. A cheap brute-force oracle gating either paradigm takes the usable rate to 100%. The survey diagrams evaluation as a downstream lifecycle stage; the data says it belongs inside the synthesis loop. Over-generate and filter, and the only real cost is the 5.5x draw, which is nothing when the verifier is cheap.

If you build agent-training environments: budget for the verifier first. Your synthesiser (symbolic or LLM) decides diversity and cost. Your verifier decides whether the tasks are worth training on at all.

## What's still off

One domain (Countdown), n=30 per paradigm, one neural batch from one model in one pass. This is a faithful spike, not a benchmark. The mechanism (construction bounds difficulty rather than setting it; LLMs misprice their own output; the verifier fixes both) is domain-general; the exact percentages are not. `min_ops` is a reasonable difficulty proxy for Countdown, not a universal one.

Full code (oracle, three synthesisers, frozen neural batch, one-command rerun): `env.py`, `evaluate.py`, `neural_batch.json`, `FINDINGS.md`.
