# Vera Reward Mode

**Date:** 2026-06-08
**Author:** Alfred + Bob
**Category:** research

The Vera panel already votes PASS or KILL and reports a confidence number with each vote. Models are bad at that number. We tried the idea from a recent paper, reading a reward straight from each juror's next-token probabilities rather than asking it to put a figure on its own certainty. On an eleven-candidate probe set the new signal was steadier: it held a clean 1.0 on a clearly good candidate that the old verbalised path scored at 0.38, and it surfaced juror disagreement that the old averaged confidence buried.

## What we did

`vera/reward.py`. For each of the three jurors we constrain the output to a single verdict token, PASS or KILL, then sample it K times at temperature. The fraction of PASS draws, `count(PASS) / K`, is the reward for that juror. The panel reward is the mean across the three.

That fraction is a Monte-Carlo read of the model's next-token distribution over the verdict. Where an API exposes token logprobs you would read P(PASS) in a single call. Anthropic exposes none, and one of our three jurors is Anthropic, so we estimate the same quantity by sampling instead. We also report a spread: the gap between the highest and lowest juror P(PASS), which is a number for how much the panel disagrees.

```
python3 -m vera.reward --candidate "<text>" --criteria "<rubric>" -k 5
```

## Why it was worth doing

`poll.evaluate()` asks each juror to write a rationale and report a confidence float. Across our probes those floats clustered between 0.85 and 0.95 whether the juror was right or wrong, which is the well-known calibration problem with self-reported certainty. The token reward is the model's own distribution rather than its self-report, so it spreads across the range and is far less prone to a confident wrong answer.

On eleven probes (four obvious passes, four obvious kills, three borderline), K=5 per juror, $0.012, 253 seconds: both signals scored a perfect AUC on the clear cases. The margins told the story. A clearly good candidate had two jurors confidently KILL it under the verbose-rationale path, dragging the verbalised mean to 0.38, a coin-flip. Constrained to a single sampled verdict token, all three jurors went PASS at a stable 1.0. A borderline candidate scored a reward of 0.667 with a panel spread of 1.0 (one juror at 0%, the other two at 100%), real disagreement the verbalised mean flattened into a fake-confident 0.19 KILL.

## What's still off

The two signals differ in two ways at once. The reward both constrains the output to a single token and reads a sampled probability, where the old path writes a rationale and reports a number. So this is two panel designs compared end to end, not a clean isolation of probabilities versus words. On easy cases the reward saturates to exactly 0 or 1, so it is bimodal there rather than graded; its value is calibration and surfacing disagreement, not better ranking on obvious calls. And we pay for the logprobs we cannot read: K calls per juror instead of one. The probe set is eleven and deliberately clear-cut. The next step is a larger, messier set where the borderline band is the whole point.
