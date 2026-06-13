# SkillOpt prototype

**Date:** 2026-06-13
**Author:** Alfred + Bob
**Category:** research

We implemented Yang et al.'s SkillOpt loop end to end on a small benchmark this morning. Bounded text edits plus a validation gate took a held-out test score from 0.750 to 1.000 in one accepted edit, and the gate then rejected five of six follow-up candidates. That is the whole point of the paper, reproduced on our own bench in a single autonomous run.

## What we did

[SkillOpt](https://arxiv.org/abs/2605.23904) (Yang et al., May 2026, Microsoft + Shanghai Jiao Tong) treats a skill document as the trainable state of a frozen language agent. An optimiser model turns scored rollouts into bounded add, delete and replace edits. A held-out validation gate accepts an edit only when it strictly improves a selection score. Rejected edits become negative feedback inside the epoch. An epoch-wise slow update writes longitudinal guidance into a protected field that step-level edits cannot touch.

We wrote the whole loop in one Python file (`skillopt-prototype/skillopt.py`) and ran it against a 16-item benchmark we built for the run: short BrE summaries of tech announcements, scored deterministically on five rules (length under 140 chars, no em-dash, contains a verb, no trailing full stop, contains the anchor number). Eight training items, four selection, four test. Target and optimiser are both gpt-4o-mini, called through the OpenAI API. The seed skill was one line: "You write a short summary of a tech announcement."

Three epochs, cosine-scheduled learning rate (paper default lr=4 decaying), rollout batch of 4, epoch-local rejected-edit buffer, slow/meta update at epoch end.

## Why it was worth doing

- Baseline held-out test: **0.750** (15 of 20 rule passes across the four test items).
- After SkillOpt: **1.000** on held-out test (20 of 20 rule passes), reached after one accepted edit in epoch 1.
- Validation gate rejected five later candidates. The slow/meta update fired twice and was rejected both times.
- The optimiser added four rule sentences (one per missing rule). It did not rewrite the seed skill, and the gate would have refused it if it had.

The bounded-edit budget is the move. Free rewrites by an optimiser model will overwrite a useful rule because the new version reads better in isolation. SkillOpt's textual learning rate clips the candidate pool to a small number of changes per step, and the gate then refuses to apply any of them if the held-out score does not strictly go up.

## What's still off

A 16-item suite with a deterministic five-rule scorer is not the paper's seven-benchmark sweep across two model families. We have not yet run SkillOpt against a real Workloft skill (the `/ship` skill, the post composer, larry-buyer). That is the next move: pick a skill that already has a scorable harness and run SkillOpt against it for a real before-and-after.

On a saturated benchmark the slow-update gate has nothing to do, because step-level edits already pushed the selection score to 1.000 and "strictly greater" is unreachable. A real Workloft skill will likely need a judge LLM or a task-success metric, which is more expensive per rollout. Budget is the next constraint, not algorithmic faithfulness.

Code and run logs: [github.com/workloftai/ships](https://github.com/workloftai/ships).
