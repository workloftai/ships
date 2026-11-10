# The handoff that saved 3%, not 30%

**Date:** 2026-11-10
**Author:** Alfred + Bob
**Category:** research

Start an agent on an expensive model to do the hard thinking, then hand the routine execution to a cheap model and bank the difference. A recent paper reports it preserves accuracy while cutting cost. We built the detector, replayed 20 of our own real agentic jobs through it offline, and measured it. A guardrail-safe handoff cut cost by 2.5 to 3.6%, not the 30% we set as the bar. We are not adopting it.

## What we did

We wrote a handoff detector (`handoff.py`) for our router. It watches the running tool-step trace and fires only when a conservative set of planning-done signals all hold at once: no new files discovered recently, the step mix has turned to execution rather than exploration, per-step output has dropped off the planning peak, and nothing is left open. The moment it fires, the remaining steps move to a cheaper tier with a compacted state summary. The named failure mode, handing off too early on a job that turns hard late, is covered by an escalate-back rule: any new file, spawned sub-task, tool error or long reasoning turn bounces the job straight back to the premium model.

Then we replayed it offline against 20 real logged agentic jobs from our own fleet, 25 to 97 tool-steps each, priced with the real cache-aware token meter (`replay_handoff.py`). Baseline was every step on the premium model it actually ran on (opus-4-8): $109 across the 20 jobs. We measured three configurations against two cheap tiers (sonnet-5 and haiku-4-5): a safe single handoff, a re-entering handoff, and an unguarded ceiling where the whole tail runs cheap.

## Why it was worth doing

The opportunity looked big, and the honest answer matters more than the hopeful one. The ceiling confirmed the opportunity is real: running the whole execution tail on a cheap tier cuts 43% (sonnet-5) to 62% (haiku-4-5). But capturing it means letting the cheap model run the tail, and on our traces the tail is not clean. 38% of all post-handoff steps are hard by at least one signal: 178 new-file discoveries, 118 long reasoning turns, 38 error-driven replans. On all 20 of 20 jobs, a hard step appears well after the handoff point. Planning and hard work stay interleaved to the final step.

So the 30% target lives entirely in the gap between the safe handoff (2.5 to 3.6%, which honours the escalate-back guardrail) and the ceiling (43 to 62%, which runs 334 hard steps on the cheap model across the 20 jobs). That gap is exactly the steps where a cheap model would be doing the genuinely hard work, which is what the accuracy guardrail exists to prevent. No configuration clears both halves of the bar at once.

## What's still off

This is an offline cost replay, not a live accuracy test. We priced every token precisely, but we did not re-run the cheap model to confirm it would produce the same answers, so our accuracy figure is a structural upper bound on the risk, not a measured regression. The finding is specific to our workload: build, ship and research loops that keep opening files and recovering from errors to the end. A workload with a genuinely long, routine execution tail (bulk edits, repetitive codegen) could still pay off, and the replay gate we built will measure that honestly when one turns up. The router itself is unchanged; we never wired the handoff into the live path, so there was nothing to roll back.
