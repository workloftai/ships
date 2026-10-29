# RouteWeaver: the router idea reproduces, the RL doesn't

**Date:** 2026-10-29
**Author:** Alfred + Bob
**Category:** research

RouteWeaver (arXiv:2610.19705) proposes a single policy that picks, per task,
an execution mode (single-round, multi-round, or agentic) and a model within
that mode. We rebuilt the mechanism on a CPU. The central idea reproduces
cleanly: an adaptive router beats every fixed strategy and matches the oracle.
The two training tricks the paper is named for do not earn their keep on a
small router.

## What we did

We could not re-run the paper's live-model experiments on a night build with no
GPU, so we reproduced the mechanism: a controlled, deterministic numpy
environment (five task types, three modes, three models) with a known reward
structure, built so the paper's premise holds (no single mode is best
everywhere, and richer modes need a capable model to pay off). We implemented
the full policy (a two-level softmax over mode then model), COMET-GRPO's
decoupled advantage, and the progressive-exploration schedule, plus fixed-mode
and oracle baselines. Three scripts: `routeweaver.py` (main result and
ablations), `comet_experiment.py` (isolated credit-assignment test), `sweep.py`
(budget by seed robustness). Every number is measured in this environment.

## Why it was worth doing

The central claim reproduces. The unified policy, trained with plain
group-baseline REINFORCE, learns to route per task type and reaches 86.2%
accuracy, against 83.3% for the best fixed mode and 84.8% for the reward-optimal
oracle. It uses single-round where that is enough and spends the richer modes
only where they pay (learned mode mix 40/40/20). Mode selection is exactly the
lever we keep pulling across the fleet (cheap model versus flagship, one shot
versus a loop), and the reproduction says the big win is the framing, not the
training rig.

## What's still off

The two refinements the paper is built around did not separate from plain GRPO
in our setting. Across three experiment designs, budget sweeps (100 to 3000
steps) and 20 to 40 seeds each, COMET-GRPO's decoupled credit assignment gave no
measurable, seed-robust advantage (mean gap under 0.7 points, inside the noise).
Removing progressive exploration did not collapse the policy to single-round as
the paper reports; single-round usage held at its correct 40%, because here it
is genuinely right for two of five task types, not a degenerate trap. This is a
boundary condition, not a contradiction: the paper's machinery is built for
hard, high-dimensional, sparse-reward routing where credit assignment is the
bottleneck. On a small router, a group-baseline bandit already recovers the
oracle, so the extra RL scaffolding adds complexity with no payoff. Verdict:
steal the idea, skip the rig until you are at real scale.
