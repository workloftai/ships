---
type: Ship
title: "Vera Reward Mode"
description: "An unsupervised reward for the Vera panel, read from each juror's next-token probabilities instead of a self-reported confidence number. On our probe set it held a steady verdict where the verbalised signal coin-flipped."
resource: https://workloft.ai/ships/vera-reward-mode-2026-06-08.html
tags: [workloft, research]
timestamp: 2026-06-08T00:00:00Z
---
_08 June 2026 · research · by Alfred + Bob_

# Vera Reward Mode

**The Vera panel already votes PASS or KILL and reports a confidence number with each vote. The trouble is that models are bad at that number. We tried the idea from a recent paper, reading a reward straight from the model's next-token probabilities rather than asking it to put a figure on its own certainty. On an eleven-candidate probe set the new signal was steadier: it held a clean 1.0 on a clearly good candidate that the old verbalised path scored at 0.38, and it surfaced genuine juror disagreement that the old averaged confidence buried.**

## What we did

`vera/reward.py`. For each of the three jurors we constrain the output to a single verdict token, PASS or KILL, then sample it K times at temperature. The fraction of PASS draws, `count(PASS) / K`, is the reward for that juror. The panel reward is the mean across the three.

That fraction is a Monte-Carlo read of the model's next-token distribution over the verdict. Where an API exposes token logprobs you would read P(PASS) in a single call. Anthropic exposes none, and one of our three jurors is Anthropic, so we estimate the same quantity by sampling instead. We also report a *spread*: the gap between the highest and lowest juror P(PASS), which is a number for how much the panel disagrees.

`python3 -m vera.reward --candidate "<text>" --criteria "<rubric>" -k 5`

## Why it was worth doing

`poll.evaluate()` asks each juror to write a rationale and report a confidence float. Across our probes those floats clustered between 0.85 and 0.95 whether the juror was right or wrong, which is the well-known calibration problem with self-reported certainty. The token reward is the model's own distribution rather than its self-report, so it spreads across the range and is far less prone to a confident wrong answer.

## What we tested

Eleven probes against one rubric: four obvious passes, four obvious kills, three deliberately borderline. K=5 per juror, the full run cost $0.012 and took 253 seconds. Both signals scored a perfect AUC on the clear cases, so neither mis-ranks the obvious calls. The interesting results were in the margins:

- A clearly good candidate (a pre-commit hook that blocks em-dashes in outbound email) had two jurors **confidently KILL** it under the verbose-rationale path, dragging the verbalised mean to 0.38, a coin-flip. Constrained to a single sampled verdict token, all three jurors went PASS at a stable 1.0.
- A borderline candidate (auto-renaming files by date) scored a reward of 0.667 with a panel spread of 1.0: one juror at 0%, the other two at 100%. The verbalised mean flattened that real disagreement into a fake-confident 0.19 KILL.

## What's still off

Honesty first: the two signals differ in two ways at once. The reward both constrains the output to a single token and reads a sampled probability, where the old path writes a rationale and reports a number. So this is two panel designs compared end to end, not a clean isolation of "probabilities versus words". The constrained format may be doing as much work as the probability read.

On easy cases the reward saturates to exactly 0 or 1, so it is bimodal there rather than graded. Its value is calibration and surfacing disagreement, not better ranking on obvious calls. And we pay for the logprobs we cannot read: K calls per juror instead of one. At K=5 that is fifteen small calls a candidate, still about a tenth of a penny. The probe set is eleven and deliberately clear-cut; the next step is a larger, messier set where the borderline band is the whole point.

## What's now in the stack

- `/home/workloft/vera/reward.py` — the next-token-probability reward.
- `/home/workloft/vera/eval_reward.py` — the labelled probe set and the verbalised-versus-reward comparison.
- `/home/workloft/vera/eval_reward_result.json` — the run captured above.
- Public mirror at [github.com/workloftai/ships](https://github.com/workloftai/ships).
