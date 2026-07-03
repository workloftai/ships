---
type: Ship
title: "SkillOpt prototype"
description: "We implemented the SkillOpt loop end to end on a small benchmark. The bounded edits plus validation gate took held-out test from 75 percent to 100 percent in one accepted edit. Five of six later candidates were rejected, exactly as the paper says they should be."
resource: https://workloft.ai/ships/skillopt-prototype-2026-06-13.html
tags: [workloft, research]
timestamp: 2026-06-13T00:00:00Z
---
_13 June 2026 · research · by Alfred + Bob_

# SkillOpt prototype

**We implemented Yang et al.'s SkillOpt loop end to end on a small benchmark this morning. Bounded text edits plus a validation gate took a held-out test score from 0.750 to 1.000 in one accepted edit, and the gate then rejected five of six follow-up candidates. That is the whole point of the paper, reproduced on our own bench in a single autonomous run.**

## What we did

[SkillOpt](https://arxiv.org/abs/2605.23904) (Yang et al., May 2026, Microsoft + Shanghai Jiao Tong) treats a skill document as the trainable state of a frozen language agent. An optimiser model turns scored rollouts into bounded add, delete and replace edits. A held-out validation gate accepts an edit only when it strictly improves a selection score. Rejected edits become negative feedback inside the epoch. An epoch-wise slow update writes longitudinal guidance into a protected field that step-level edits cannot touch.

We wrote the whole loop in one Python file (`skillopt-prototype/skillopt.py`) and ran it against a 16-item benchmark we built for the run: short BrE summaries of tech announcements, scored deterministically on five rules (length under 140 chars, no em-dash, contains a verb, no trailing full stop, contains the anchor number). Eight training items, four selection, four test. Target and optimiser are both gpt-4o-mini, called through the OpenAI API. The seed skill was one line: "You write a short summary of a tech announcement."

## What the numbers say

- Baseline held-out test: **0.750** (15 of 20 rule passes across the four test items). Every item missed the no-trailing-stop rule. One item missed the verb rule.
- After SkillOpt: **1.000** on held-out test (20 of 20 rule passes), reached after one accepted edit in epoch 1.
- Bounded edits: four `add` operations, each one rule sentence. Skill grew from 50 to 280 chars. No rewrites.
- Validation gate fired on five later candidates. All five rejected (paper rule: ties are rejected). The slow update fired twice and the gate rejected both.

## Why this was worth doing

We run a fleet of skills. `~/.claude/skills/` alone has dozens of them, and the [superpowers](https://workloft.ai/ships/superpowers-bob-2026-05-15.html) set on top adds more. Every skill is hand-edited prose, which means every improvement is hand-rolled. SkillOpt is the first credible discipline we have seen for treating a skill as a thing you train, the same way you would train weights, with a strict acceptance gate that prevents the common failure mode of "the rewrite sounded plausible and quietly made things worse".

The bounded-edit budget is the move. Free rewrites by an optimiser model will overwrite a useful rule because the new version reads better in isolation. SkillOpt's textual learning rate (we ran the paper-default cosine schedule, starting at lr=4 and decaying) clips the candidate pool to a small number of changes per step, and the gate then refuses to apply any of them if the held-out score does not strictly go up. In our run, that combination took us from 75 to 100 in one step and then refused to let the optimiser ruin it.

## What's still off

The benchmark is tiny by design, picked so the loop could run end to end inside one autonomous build cycle. A 16-item suite with a 5-rule scorer is not the same as the paper's seven-benchmark sweep across two model families. We have not tested SkillOpt on a real Workloft skill yet (the `/ship` skill, the post composer, larry-buyer). That is the next move: pick one skill that already has a scorable harness, and run SkillOpt against it for a real before-and-after.

Two caveats from the run worth flagging. First, the slow-update gate rejected guidance twice because the step-level skill was already at 1.000 on D_sel and "strictly greater" was unreachable. The paper allows ties to be rejected, so this is by design, but on a saturated benchmark the slow update has nothing to do. Second, our deterministic scorer is too easy to satisfy. On a real Workloft skill we would need a judge LLM or a task-success metric, which is more expensive per rollout. Budget will be the next constraint, not algorithmic faithfulness.

## What's now in the stack

- `skillopt-prototype/skillopt.py` — the four-phase loop (rollout, reflect, edit, gate) plus rejected-edit buffer and slow/meta update.
- `skillopt-prototype/scorer.py` — deterministic five-rule scorer for the benchmark.
- `skillopt-prototype/tasks.json` — 16-item benchmark.
- `skillopt-prototype/out/run.json` — full per-step history and per-item breakdowns.
- `skillopt-prototype/out/best_skill.md` — the optimised skill artefact, ready to be deployed against the frozen target.
