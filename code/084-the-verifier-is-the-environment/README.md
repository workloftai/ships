# The Verifier Is the Environment — reproduction

Minimal reproduction of the synthesis/evaluation core of *Agentic Environment
Engineering for LLMs* (arXiv:2606.12191), on the Countdown numbers puzzle.

## Run

```bash
python3 env.py        # smoke-test the brute-force oracle + symbolic synthesiser
python3 evaluate.py   # score symbolic vs neural vs verified_symbolic -> results.json
```

No dependencies beyond the Python 3 standard library. Fully deterministic: the
neural batch is frozen in `neural_batch.json` (one pass from Claude, no verifier),
so `evaluate.py` reproduces the published numbers exactly.

## Files

- `env.py` — the deterministic brute-force solver (ground-truth difficulty
  oracle), the symbolic synthesiser, and the verifier-gated variant.
- `neural_batch.json` — 30 puzzles authored by an LLM in one pass, no checking.
- `evaluate.py` — scores all three paradigms on validity, difficulty
  calibration, and diversity.
- `FINDINGS.md` — the writeup and the headline table.
- `results.json` — last run's output.

## Headline

| paradigm | validity | usable | diversity | difficulty match |
|---|---|---|---|---|
| symbolic | 100% | 77% | 100% | 33% |
| neural | 93% | 80% | 93% | 7% |
| verified_symbolic | 100% | 100% | 90% | 100% |

Neither generator can price the difficulty of its own tasks. A cheap verifier in
the loop takes the usable rate to 100%. The load-bearing component is the
verifier, not the synthesiser.
