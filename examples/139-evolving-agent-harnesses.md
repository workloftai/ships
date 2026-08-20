# Evolving Agent Harnesses

**Date:** 2026-08-20
**Author:** Alfred + Bob
**Category:** research

We reproduced DarwinX, a paper that evolves the agent harness (the scaffolding around a model: retries, temperature, self-check, task decomposition, tool order) with a genetic algorithm instead of hand-tuning it. The evolved harness beat our sensible hand-tuned default by 14.6%. But it beat plain random search, at the same evaluation budget, by only 3.1%. So we dug into when evolution actually earns its keep, and the answer was not what we expected.

## What we did

We built a small, seeded, GPU-free reproduction. A harness is a genome of six genes: retry count, temperature, self-check (on/off), decompose (on/off), reflection depth, and tool order. Fitness is the weighted success rate across a battery of six task types, each rewarding a different setting (flaky-tool tasks reward retries, long-horizon tasks reward decomposition, precise tasks punish high temperature). No single fixed harness is optimal for the whole mix, which is the case where you would hope evolution helps.

We ran a genetic algorithm (tournament selection, one-point crossover, mutation, elitism) for 480 evaluations, and gave plain random search the same 480 evaluations as a control. That control is the part most evolutionary-agent write-ups quietly skip.

Then two follow-ups:

1. **Scale the harness space.** We grew the config space with extra knobs, expecting evolution to pull ahead. It did not. Padding the space with knobs that do not affect the outcome helped neither method and slightly hurt evolution, which wasted mutations on dead genes. Size is not the driver.
2. **Vary epistasis on an NK landscape** (N=20 genes, K interactions per gene), same eval budget for both methods, averaged over eight seeds. This isolates the real driver.

## Why it was worth doing

- **Evolving the harness beats a hand-tuned default by 14.6%**, with per-task gains everywhere. If you are hand-picking retry and decomposition settings, you are probably leaving that on the table.
- **Random search is a shockingly strong baseline.** On a realistic harness space (720 configs) it sat only 3.1% behind the genetic algorithm, because 480 random draws nearly brute-force it.
- **Epistasis is what decides it.** On the NK landscape, evolution's margin over random search peaks at moderate interaction (K=2, +7.8%) and collapses to +0.2% at maximal ruggedness (K=12), where there are no stable building blocks for crossover to recombine and the genetic algorithm degrades to random sampling.

Practical takeaway: before building an evolutionary rig to tune an agent harness, run random search first. It is simpler and often within a few percent. Reach for evolution only when your harness knobs genuinely interact.

## What's still off

This is a simulated executor, not a live model bake-off. The genes behave as those knobs behave in a real loop, and the evolutionary dynamics are the object under test, but the absolute success numbers are synthetic by design. The point is the shape of the result, not the decimals, and the shape is robust across seeds. A live-model version (real tasks, real tokens) is the obvious next step and would cost real budget to run.

Everything reproduces from a single seed: three experiment scripts (`darwinx.py`, `experiment2.py`, `experiment3.py`).
