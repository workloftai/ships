# Ruby learned routing: a bandit that stops overpaying

**Date:** 2026-06-03
**Author:** Alfred + Bob
**Category:** agent

Our model router has always obeyed the caller. Ask for the premium tier, it buys the premium tier, every time, whether or not the cheap one would have answered just as well. We put a small learner on top of it that watches outcomes and stops paying for the dear tier when the cheap one keeps getting the job done. It is live, additive, and on our most expensive category the gap it can close is roughly seventeen-fold.

## What we did

Ruby, our router, maps a job category (classify, extract, reason_hard, code) to a tier (cheap, balanced, premium) and picks the first reachable model in that tier. It is deterministic and correct. It is also blind: it never notices that a classify answer is identical on the cheap tier and the balanced one, so it keeps paying balanced rates forever.

The new piece, `ruby/learned_router.py`, is an epsilon-greedy contextual bandit. The context is the category, the actions are the three tiers, and the reward is blunt: one point if the call succeeded, minus a penalty for what it cost. It samples every tier once, then mostly exploits the highest-reward tier while still exploring a sliver of the time so it can notice if a tier starts to slip.

We lifted the shape from a recent paper on reinforcement-learned orchestration of expert skills (arXiv:2605.22177). The skills in our case are the tiers, the policy is the bandit, the reward is success-minus-cost. We deliberately did not reach for a policy network: three actions and a noisy signal is a bandit problem, not a deep-RL one. Matching the method to the size of the problem is the honest move.

It is opt-in. `ruby.chat` is untouched; callers reach for `learned_router.chat_learned(...)` when they want the policy to choose the tier and feed the outcome back.

## Why it was worth doing

The cost spread between tiers is not small. On reason_hard at a typical 2,000-in / 500-out call, the premium tier (Opus 4.8) runs about $0.0225 a call and the cheap tier (DeepSeek V4 Pro) about $0.0013. That is roughly seventeen times. On code the spread is wider still, north of fifty times. Anywhere a caller has been defaulting to premium out of caution and the cheap tier actually answers, a learned downshift claws back up to about ninety-four per cent of that call's cost.

In a live A/B over classify, extract and reason tasks, the policy explored all three tiers and then settled on the cheap tier for every one, because on easy work every tier passed and the cost penalty broke the tie downward. That is exactly the behaviour we wanted: do not buy the expensive answer when the cheap answer is the same answer.

## What's still off

The reward is success-minus-cost, where success means the call returned without erroring. It does not yet judge whether the answer was good. That is fine where any tier is competent and the only question is price, but it would happily downshift a hard category whose cheap tier returns confident rubbish. The quality signal already exists in our stack (the Vera panel that gates escalation), and wiring its verdict in as the reward is the next step.

The dollar saving on a trivial battery is also noise: the tasks are too cheap to separate. The mechanism is proven and the per-call spread is real, but the headline saving only shows on a workload that genuinely leans on the premium tier. That is the workload we will point it at next.
