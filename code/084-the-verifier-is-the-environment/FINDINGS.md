# Findings — reproducing the synthesis/evaluation core of the Agentic Environment Engineering survey

**Paper:** *Agentic Environment Engineering for LLMs: A Survey of Environment
Modeling, Synthesis, Evaluation, and Application* (arXiv:2606.12191).

The survey names two automated environment-synthesis paradigms — **symbolic**
and **neural** — and says each needs "different environment evaluation methods."
It quantifies neither. This reproduction makes the claim concrete on one
cleanly-verifiable task domain and measures what the survey leaves abstract.

## Setup

- **Domain:** the Countdown numbers puzzle. A task instance is four integers
  (1–9) and a target. It is *valid* iff some arithmetic expression over a
  non-empty subset of the numbers (each used once, `+ - * /`, integer-only)
  equals the target. Standard subset rules.
- **Evaluation harness:** a deterministic brute-force solver (`env.py:solve`)
  that returns `(solvable, min_ops)` — ground truth, no model. `min_ops` is the
  *true* difficulty: the fewest binary operations any solution uses.
- **Three synthesisers, all asked for the same nominal difficulty (3 ops),
  n=30 each:**
  - `symbolic` — plant a 3-op solution, read the task off it.
  - `neural` — a real LLM (Claude, one pass, **no verifier, no calculator**)
    asked to author 30 three-op puzzles. Batch frozen in `neural_batch.json`.
  - `verified_symbolic` — symbolic candidates filtered by the oracle to keep
    only those whose *true* min-ops is exactly 3 (verifier-in-the-loop).

Reproduce: `python3 evaluate.py` (writes `results.json`). Fully deterministic.

## Results

| paradigm | validity | usable rate¹ | diversity | difficulty match² |
|---|---|---|---|---|
| symbolic | **100%** | 77% | 100% | 33% |
| neural | 93% | 80% | 93% | **7%** |
| verified_symbolic | **100%** | **100%** | 90% | **100%** |

¹ solvable AND not trivial (true min-ops ≥ 2). ² true min-ops == the claimed 3.

True-difficulty distribution (where the "3-op" puzzles actually landed):

- symbolic: `{0:2, 1:5, 2:13, 3:10}` — 20/30 had a subset shortcut; 7 trivial.
- neural: `{1:4, 2:22, 3:2}` — clusters at 2 ops; only 2/30 truly needed 3.
- verified_symbolic: `{3:30}` — exact, at the cost of drawing **165 candidates
  to keep 30** (5.5× over-generation).

## What this shows (that the survey doesn't)

1. **Validity and difficulty are different problems, and only validity comes
   for free from construction.** Symbolic synthesis is solvable-by-construction
   (100% valid) but *not* difficulty-calibrated: planting a 3-op solution only
   sets an *upper bound*, because a shorter subset solution usually exists. Just
   33% of "3-op" symbolic puzzles actually need 3 ops.

2. **Neural synthesis controls neither.** The LLM emitted 2/30 impossible
   targets and *systematically overestimated* difficulty — it thought it was
   writing 3-op puzzles; 22/30 were solvable in 2. An LLM cannot price the
   difficulty of a puzzle it just invented without search.

3. **The verifier — not the synthesiser — is the load-bearing component.** A
   cheap brute-force oracle gating *either* paradigm takes usable-rate to 100%.
   The survey diagrams evaluation as a downstream lifecycle stage; the data says
   it belongs *inside* the synthesis loop. Over-generate-and-filter is the move,
   and the only real cost is the 5.5× draw — trivial when the verifier is cheap.

**Takeaway for anyone building agent-training environments:** budget for the
verifier first. Your synthesiser (symbolic or LLM) decides diversity and cost;
your verifier decides whether the tasks are worth training on at all. Ship the
oracle before you ship the generator.

## Caveats

- One domain (Countdown), n=30 per paradigm, one neural batch from one model in
  one pass — this is a faithful spike, not a benchmark. The *mechanism* (planting
  bounds difficulty; LLMs misprice difficulty; the verifier fixes both) is
  domain-general; the exact percentages are not.
- `min_ops` is a reasonable difficulty proxy for Countdown, not a universal one.
