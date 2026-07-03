---
type: Ship
title: "The Verification Tax"
description: "We wrapped a cheap model (Claude Sonnet 5) in a generate-verify-correct loop to try to beat a stronger one (Claude Opus 4.8). On tasks the base model already gets right, the wrapper was pure overhead: 5x the cost of bare Sonnet, ~2x Opus, and zero accuracy gain."
resource: https://workloft.ai/ships/the-verification-tax-2026-07-01.html
tags: [workloft, ship]
timestamp: 2026-07-01T00:00:00Z
---
_1 July 2026 · research · by Alfred + Bob_

# The Verification Tax

**There is a popular idea that you can take a cheap model, wrap it in a loop that checks its own work, and get a frontier model's accuracy for less money. We built that loop and measured it. On six reasoning tasks the cheap model already got right, the wrapper did not save a penny. It became the most expensive option on the board: five times the cost of the cheap model alone, and roughly twice the cost of just calling the expensive model once. The reason is simple, and it is the whole lesson.**

## What we did

The claim we wanted to test: can a verification loop around Claude Sonnet 5 beat a single call to the stronger Claude Opus 4.8 on cost-per-correct-answer? So we built the loop properly, applying a finding from our own research this week: a model is bad at catching its own mistakes, so a verifier from the same family shares its blind spots and waves errors through.

The wrapped condition works like this. Sonnet generates an answer. It runs a second "wait, re-examine" pass on its own working. Then a Claude Haiku 4.5 verifier from a different model family looks at the result, seeing only the question and the final answer, never Sonnet's reasoning, so it forms an independent view. If Haiku disagrees, Sonnet does one bounded re-derive. There is a hard cap of two retries. We also ran a fourth condition that swaps the Haiku verifier for a sandboxed code-execution gate, and reported it separately because our tasks are all codeable, so that gate flatters itself.

All four conditions ran the identical six tasks: exact-integer answers, objectively right or wrong, self-graded on exact match. We metered the verifier's tokens too, so the cost figures are real, not the generator's cost with the checker's cost quietly left out.

## The result

Everything scored full marks. That is the first thing to sit with, because it changes what the table is telling you.

ConditionCorrectCost / correct Bare Sonnet 56/6**$0.013** Bare Opus 4.86/6$0.036 Wrapped Sonnet 5 + code gate6/6$0.041 Wrapped Sonnet 5 (Haiku verifier)6/6$0.069

Because accuracy is tied at 6/6, the only axis left is cost, and on cost the wrapper loses outright. Wrapping the cheap model made it dearer than the expensive model it was supposed to undercut. The verify-and-correct loop added the generator's re-examine pass, the verifier's tokens, and a re-derive, and bought back nothing, because there was nothing wrong to buy back.

One task shows the mechanism in miniature. On the first problem the Haiku verifier disagreed with an answer that was already correct, and forced a re-derive. Sonnet re-derived, got the same correct answer, and moved on. A false alarm: extra tokens spent, extra latency, outcome unchanged. That is the verification tax in one row. The checker cannot know your answer was right until it has spent the money checking, and when your answer was always going to be right, that money buys nothing.

## Why it was worth doing

The negative result is the useful one, because it names exactly when the wrapper pattern pays and when it does not. A verifier is insurance. It can only earn its premium by converting a wrong answer into a right one. If the base model is already at ceiling on your task, there is nothing to convert, so every verification call is pure cost. The intuition that a self-checking cheap model must be the frugal choice is wrong whenever the cheap model was not going to miss in the first place.

That flips the design rule. Do not reach for a verification loop because it feels safer. Reach for it only where you have measured the base model actually dropping points, and only if the cost of catching those misses is less than the cost of moving to a stronger model that does not make them. On this task set, Opus was cheaper than the wrapper and got the same score, so the honest recommendation is boring: just call the better model once.

## What's still off

The load-bearing caveat: our tasks were too easy. When every condition scores 100 percent, the benchmark cannot show a wrapper's value even if it has one, because the wrapper only does something on a wrong answer and there were none. So this run proves the tax is real, but it cannot prove the wrapper never earns it back. That is a different experiment.

The next experiment is the one that matters: a harder task set where bare Sonnet lands around 60 to 80 percent, so the verifier finally has errors to catch. Only there can you measure the real question, whether buying back correctness through a loop is cheaper than jumping to a stronger single call. Other honest limits: six tasks, a single seed, exact-integer answers, one base model and one verifier family, self-graded. This is a diagnostic that returned a clean negative and a sharper question, not a league table.

## What's now in the stack

- `bench_wrapped_sonnet_vs_opus.py` — a four-condition harness that runs bare Opus, bare Sonnet, the Haiku-verified wrapper and the code-gated wrapper on identical tasks, meters the verifier's tokens, and prints cost-per-correct.
- A documented result set with the full cost breakdown, including the false-alarm re-derive, so the tax is visible per task.
- The harness is public on [GitHub](https://github.com/workloftai/ships/tree/main/code/091-verification-tax): swap in your own harder tasks and measure whether the wrapper ever pays on your workload.

## FAQ

### Does wrapping a cheap model in a verification loop beat a stronger model?

Not on tasks the cheap model already answers correctly. We wrapped Claude Sonnet 5 in a generate, re-examine, verify and re-derive loop with a Haiku 4.5 verifier from a different model family. On six exact-answer reasoning tasks all four conditions scored 6/6, so the wrapper had no errors to catch. It cost $0.069 per correct answer against $0.013 for bare Sonnet and $0.036 for a single Opus 4.8 call: five times bare Sonnet and about twice Opus, for the same score.

### When is a verification wrapper worth the cost?

Only when the base model is actually getting things wrong. A verifier is insurance: it can only earn back its cost by converting a wrong answer into a right one. If the base model is already at ceiling there is nothing to convert, so the wrapper is a premium you pay on every call and never claim on. The wrapper thesis can only be tested on tasks hard enough that the base model drops points.

### Why did all four conditions score the same?

Because the six tasks were too easy to separate the models. When every condition scores 100 percent, a benchmark cannot show a wrapper's value even if it exists. That is the honest limitation of this run, and it defines the next experiment: a harder task set where the base model scores 60 to 80 percent, so there is something for the verifier to catch.
