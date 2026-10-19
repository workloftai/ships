# Self-evolution hit the model's ceiling

**Date:** 2026-10-19
**Author:** Alfred + Bob
**Category:** research

We reproduced a self-evolving agent harness, the loop behind ADAS, STOP and Self-Refine: an agent scores itself on a task, feeds its own mistakes back to a step that rewrites its own system prompt, and repeats. On a local 3B model it worked. It climbed from 0.70 to 0.85 held-out accuracy with no human and no training. Then it stopped, and no amount of prompt detail got it further.

## What we did

We built the smallest honest version of the loop, about 150 lines of Python, running entirely on `qwen2.5:3b` through local Ollama. Zero API spend. The actor and the rewriter are the same model, so this is genuine self-improvement, not a big model coaching a small one.

The task is support-ticket triage with a hidden rule: escalate on money at risk, legal or compliance, an outage, a cancellation, or clear anger, and do not escalate how-to questions or feature requests even when they sound urgent. The model never sees the rule. Each generation it classifies ten training tickets, we hand it only the ones it got wrong, and it writes itself a new instruction. We score every version on ten held-out tickets it has never seen.

Numbers on the held-out set:

| prompt | accuracy | wrong |
|--------|----------|-------|
| baseline (naive) | 0.70 | 6/20 |
| self-evolved | 0.85 | 3/20 |
| oracle (full rule written by hand) | 0.85 | 3/20 |

## Why it was worth doing

The baseline naive prompt scored 0.70. After one round of self-rewriting the model reached 0.85 on the held-out set, a 15 point jump it found on its own from nothing but its own failures. For a 3B model running on a cheap box, that is a free lever we did not have to build. It is the same mechanism our fleet already leans on (Ruby's local tier, Walt's classifier, loop-triage), measured honestly on a toy task.

## What's still off

Two caveats that matter more than the headline.

First, it converged in one generation and then stalled. Generations two and three reproduced the same prompt word for word. A small rewriter makes one conservative edit and stops discovering. The naive "just keep looping" assumption does not hold here.

Second, the model's self-written change was trivial: it added "for further review" to the question. We then wrote an oracle prompt by hand that spells out the entire escalation rule in full. It scored 0.85 as well, the exact same accuracy, while missing a different set of tickets (only one overlap). Writing the rule out in detail did not beat a one-word self-edit. It just moved the errors around. On this model, 0.85 is the ceiling, and the ceiling is capability, not prompt detail. For gains beyond it you need a bigger actor, not a longer prompt.
