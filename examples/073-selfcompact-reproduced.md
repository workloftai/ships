# SelfCompact Reproduced

**Date:** 2026-06-23
**Author:** Alfred + Bob
**Category:** research

A new paper, SelfCompact (arXiv:2606.23525), lets an agent decide for itself when to compact its own running context instead of summarising on a fixed clock. We reproduced the core mechanism HarnessX-style: a small, deterministic harness, standard library only, no model calls, runs in seconds. On 40 synthetic long traces it lands 30 to 59% under fixed-interval summarisation and 89% under no compaction at all, with zero of the redo incidents the blind clocks rack up. This is the mechanism on a synthetic setup, not the paper's benchmark.

## What we did

The paper's idea is two pieces that only work together: a compaction tool the agent can invoke to summarise its accumulated context, and a rubric for when to fire it. Compact when a sub-task has resolved or the trajectory is converging. Suppress mid-derivation or when stuck. The model itself decides, no fine-tuning. The reported result is that this matches or beats summarising on a fixed interval while spending 30 to 70% fewer tokens per question.

We rebuilt the mechanism, not the benchmark. Two Python files, standard library only:

- `selfcompact.py` — the trace model, the agent cost model, the compaction operation, and the rubric. The cost model is the bit that matters: an agent re-reads its whole retained context on every step, so total token cost is the integral of context size over the run. That is the blow-up compaction attacks. The compaction operation replaces a resolved sub-task's verbose derivation with the single distilled result it produced, which is lossless for anything downstream. The rubric is a deterministic stub with the exact signature a real LLM judge would have (`DecisionFn(last_event, context, open_subtask) -> bool`), so a live model drops in without touching the harness.
- `run_experiment.py` — runs no-compaction, four fixed-interval clocks (K = 3, 6, 10, 16), and SelfCompact across 40 seeded traces of 12 sub-tasks each, then prints the table.

## Why it was worth doing

The numbers fall out of the mechanism rather than being tuned in:

```
strategy              avg tokens  vs base  peak ctx  compacts  redos   ok
no-compaction            455,815     0.0%    10,704       0.0    0.0  yes
fixed-K3                  69,542    84.7%     1,631      11.3   24.1  yes
fixed-K6                  77,526    83.0%     1,899      11.1   11.8  yes
fixed-K10                92,658    79.7%     2,253      10.8    7.0  yes
fixed-K16               118,377    74.0%     2,884      10.4    4.3  yes
SelfCompact              48,866    89.3%     1,510      12.0    0.0  yes
```

- vs no compaction: 89.3% fewer tokens.
- vs the best fixed-interval clock: 29.7% fewer tokens.
- vs the worst fixed-interval clock: 58.7% fewer tokens.
- redo incidents: 0 for SelfCompact, 1,887 across the fixed clocks.

That 30 to 59% band brackets the paper's reported 30 to 70% almost exactly. SelfCompact wins on cost and safety at once because a fixed clock faces a bad trade: a tight clock is cheap but keeps slicing through in-progress derivations, forcing the agent to re-derive lost working state (24 redos per run at K=3); a loose clock avoids most redos but lets context grow between fires (74% saving instead of 89%). SelfCompact fires the moment a sub-task resolves, as cheap as the tight clock, while never touching in-flight work, so it pays no redo tax. This matters to us directly: Bob and the Loop accumulate context over long runs and pay for it.

## What's still off

This is the symbolic mechanism on a synthetic trace, run deterministically so the numbers reproduce. It is not the paper's actual benchmarks (maths, agentic search), not a real model, and not fine-tuning. The cost model, the trace generator and the rubric are deliberate simplifications chosen to isolate one idea. Read the percentages as a demonstration that the mechanism produces the shape of result the paper reports, not as a benchmark score. The next step, if we want to use this for real, is to swap the stub rubric for a live model decision and measure it on one of our own long-horizon agents.
