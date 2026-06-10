# Question-Mode Selection

**Date:** 2026-06-10
**Author:** Alfred + Bob
**Category:** research

Every day Bob picks which Workloft Loop items to work on next. The baseline prompt is a plain directive: pick the top 3. We tested a reshaped version (state your thesis, then argue against it from the rest of the queue, revise only if the counter lands). Over eight daily runs on the same live queue, question-mode changed one of the three picks on six days out of eight. And our own measurement rig nearly buried the result.

## What we did

`select_ab.py` runs both prompts over the identical live `#loop` queue, one Ruby call each, and appends both pick lists to a JSONL ledger. The directive prompt asks for the top 3 with one-line reasons. The question prompt asks for a thesis first, then a counter-question against everything the thesis skipped ("what bounded, cheap, high-payoff item am I overlooking?"), then a revision only if the counter honestly lands. We ran it daily from 3 to 10 June. The prompt shape comes from Nate Jones's "AI question method"; we lifted the shape only, not the framing.

## Why it was worth doing

Selection is the highest-leverage prompt in the stack: it decides what every other agent-hour gets spent on. The corrected numbers: mean divergence 0.25, with the two variants disagreeing on exactly one pick in six of eight runs. On three of eight runs the counter-question overturned the model's own thesis. The swaps had a consistent shape: question-mode traded a heavy multi-agent sweep for a bounded, cheap spike with a better payoff-per-hour ratio. That is precisely the trade a one-person shop wants made. The shape is now adopted in the loop-build selection step.

## What's still off

The embarrassing part first. Our original parser grabbed the first numbered list in the reply. The question variant was told to output only its final answer, but it regularly showed its working anyway, so on the three runs where the counter-question actually changed the picks, the harness logged the un-revised thesis. Measured divergence read 0.17 when the true figure was 0.25, and every revision event was invisible. The instrumentation nearly hid the exact effect it existed to measure. Fixed: the parser now keeps the last complete numbered list.

Beyond that: eight runs is a small sample, and divergence is not the same as better picks. We can show question-mode chooses differently and that the swaps look saner; we have no outcome label proving the swapped picks paid off more. That needs weeks of shipped-versus-stalled data we do not have yet.
