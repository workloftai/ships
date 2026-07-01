# 091 · verification-tax

An honest cost benchmark for the popular idea that you can wrap a **cheap model
in a loop that checks its own work** and beat a **stronger model** on
cost-per-correct-answer.

The harness runs four conditions on the same set of exact-answer reasoning
tasks:

- **bare Opus 4.8** — one call, the frontier baseline.
- **bare Sonnet 5** — one call, the cheap baseline.
- **wrapped Sonnet 5** — generate, then a "Wait" self re-examination pass, then a
  **Claude Haiku 4.5 verifier from a different model family** that sees only the
  question and the final answer (never Sonnet's reasoning, so it does not inherit
  Sonnet's blind spots), then one bounded re-derive if the verifier disagrees,
  with a hard two-retry cap.
- **wrapped Sonnet 5 + code gate** — same, but the verifier is a sandboxed
  Python execution gate instead of Haiku. Reported separately because these
  tasks are all codeable, so that gate flatters itself.

Every condition is self-graded on exact match, and the verifier's tokens are
metered too, so the cost-per-correct figures are real, not the generator's cost
with the checker's cost quietly left out.

## The finding

On this task set all four conditions scored **6/6**. Because accuracy is tied,
the only axis left is cost, and on cost the wrapper loses outright:

| Condition | Correct | Cost / correct |
|---|---|---|
| Bare Sonnet 5 | 6/6 | **$0.013** |
| Bare Opus 4.8 | 6/6 | $0.036 |
| Wrapped Sonnet 5 + code gate | 6/6 | $0.041 |
| Wrapped Sonnet 5 (Haiku verifier) | 6/6 | $0.069 |

Wrapping the cheap model made it dearer than the strong model it was meant to
undercut: about **5x** bare Sonnet and **~2x** a single Opus call, for the same
score. On one task the Haiku verifier even disagreed with an answer that was
already correct and forced a re-derive that returned the same answer: a false
alarm that cost tokens and changed nothing.

## Why

A verifier is insurance. It can only earn its premium by converting a **wrong**
answer into a right one. If the base model is already at ceiling on your task,
there is nothing to convert, so every verification call is pure cost. The
intuition that a self-checking cheap model must be the frugal choice is wrong
whenever the cheap model was not going to miss.

## The honest limit

These six tasks were too easy: every condition scored 100%, so the wrapper had
no errors to catch. This run proves the tax is real; it **cannot** prove the
wrapper never earns it back. That needs a harder task set where bare Sonnet
lands around 60 to 80 percent. Swap your own tasks into `TASKS` and measure
whether the wrapper ever pays on your workload.

## Run it

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 bench_wrapped_sonnet_vs_opus.py
```

`results.json` in this folder is the exact output from the run written up in the
ship. Six tasks, a single seed, exact-integer answers, one base model and one
verifier family: a diagnostic, not a league table.
