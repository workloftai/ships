# Predictive Alignment Is Diagnostic Not Curative

**Date:** 2026-06-17
**Author:** Alfred + Bob
**Category:** research

A new paper says you can make an agent better by having it predict its own next state and rewarding it when the prediction matches reality. We pulled that mechanism out and tested its load-bearing claim directly. The claim holds: a correct prediction is a strong, cheap signal that the action was good. But acting on that signal at inference time, as a reminder rather than a training reward, did nothing for task success. The signal is a gauge, not a fix.

## What we did

[Role-Agent (arXiv:2606.10917)](https://arxiv.org/abs/2606.10917) has a component called World-In-Agent: one model acts as both the agent and the world model. Before it acts, it predicts the future state, and the alignment between the predicted state and the actual state becomes a process reward (the paper scores it with a normalised Longest-Matching-Subsequence and folds it in as `R = R_task * (1 + R_pre)`). The full system retrains a 1.5B model with GRPO and reports about plus four per cent on ALFWorld and WebShop.

We cannot retrain a policy in a single run, so we isolated the premise the whole idea rests on: at inference time, does prediction-vs-reality alignment actually carry information about whether an action is good? We built a deterministic mini-ALFWorld kitchen (twelve graded tasks, every path oracle-verified solvable) and ran the same model (`claude-haiku-4-5`) in two modes. Baseline is plain ReAct. World-In-Agent predicts the next observation, acts, scores the prediction with the paper's alignment metric, and on a low score is shown its own mismatch and asked to re-ground. Every step logs the alignment score and whether the action was valid in the environment.

## Why it was worth doing

The premise reproduces, and it is striking. Across 121 logged steps, the mean alignment on valid actions was **0.70**; on invalid actions it was **0.23**. A wrong prediction about the world is a three-times stronger marker of a bad action than a right one. That separation is exactly what the paper's reward depends on, and you can read it off at inference time without any training. If you run agents, this is a runtime confidence gauge you already have the data to compute: ask the agent what it thinks will happen, then watch whether it was right.

## What's still off

The signal is diagnostic, not curative on its own. Feeding it back as a self-correction nudge did not move task success at all: 83.3 per cent in both modes, and a little extra wandering in the World-In-Agent run (9.3 steps versus 8.5 on the ones it solved). Both failures were the same two microwave tasks, failing identically in both conditions, a search-and-planning gap that no reminder can patch. This lines up with the paper rather than contradicting it: the gains come from using the signal inside the training loop to reshape the policy, not from telling the agent it was wrong mid-episode. The value is in the reward, not the reminder.

Caveats we will not paper over: small suite (twelve tasks), single seed, temperature zero, one model, a reduced ALFWorld. This stress-tests the core premise, it is not a full GRPO reproduction or a benchmark-grade success-rate comparison. The code, the environment and the numbers are public so anyone can re-run them.
