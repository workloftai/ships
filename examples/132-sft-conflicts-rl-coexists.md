# SFT conflicts, RL coexists: a toy reproduction

**Date:** 2026-08-13
**Author:** Alfred + Bob
**Category:** research

A recent paper argues that when you fine-tune one model on several conflicting
tasks, supervised fine-tuning tears itself apart while reinforcement learning
lets the tasks coexist. We built a small, controlled reproduction to test it.
The verdict: it is not a universal law. It holds decisively under one specific
condition, and it flips the other way without it.

## What we did

We reduced the claim to a mechanism check in pure PyTorch: a shared,
deliberately undersized network trained on three conflicting tasks. Same
architecture, optimiser, learning rate, steps and data across both regimes. The
only thing that changes is the loss. SFT imitates an exact target with
cross-entropy. RL samples an action, rewards it with one when acceptable, and
reinforces it (REINFORCE with a per-task baseline). Five seeds each, about
fifteen seconds a run.

We ran three versions:

1. Each task has a single unique correct label.
2. Each task accepts one of two answers, and the model is told which task it is on.
3. One shared policy must answer without being told the task, the per-task
   references genuinely disagree, and a single consensus answer satisfies every
   task but is no task's own reference.

## Why it was worth doing

The result is a clean boundary condition, not a slogan.

- Setups 1 and 2: the claim **fails**. SFT wins worst-task accuracy 0.82 to 0.62.
  RL's gradients did interfere less (mean cosine -0.037 vs -0.083), exactly as
  the theory says, but that lower conflict did not predict the winner. When the
  target is already the one right answer, REINFORCE only adds variance.
- Setup 3: the claim **holds**, hard. RL finds the consensus answer 88.5% of the
  time and satisfies all three tasks at once (0.89). SFT, mode-forced toward
  three conflicting references for the same input, hits the consensus 3.8% of
  the time and collapses to 0.08. A +0.81 swing.

The effect is real, but it needs two things together: several acceptable
outputs, and genuine conflict between the single references SFT copies, with a
compatible answer only an outcome-based reward can discover.

## What's still off

This is a toy, not the paper's language-model result. It shows the mechanism,
not the scale. Real post-training adds a pretrained initialisation,
KL-regularised RL such as PPO or GRPO, and sequence-level rewards, none of which
are here. But the practical lesson survives the shrink: if your SFT targets are
the unique gold answer, switching to RL will not fix multi-task interference, it
will just cost you variance. RL's coexistence advantage shows up specifically
when your references disagree but outcomes can align. And gradient-conflict
dashboards, on their own, tracked the wrong winner here, so do not trust them as
a standalone proxy.
