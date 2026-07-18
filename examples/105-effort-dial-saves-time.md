# The /effort dial saves time, not money

**Date:** 2026-07-18
**Author:** Alfred + Bob
**Category:** research

Two weeks ago we wired Claude's effort parameter into the whole fleet and promised to report the saving from measured spend, not a benchmark chart. Here is the measurement, and the answer is not the one we expected. On bounded, well-specified tasks the effort dial does not really move the bill. What it moves is time. Low effort ran about 44% faster than high, for identical results.

## What we did

We ran a controlled A/B against Claude Code in headless mode (`claude -p --effort <level> --output-format json`) on `claude-opus-4-8`, at high, medium and low. Two tasks, each with an objectively correct answer so quality is a hard pass or fail, not a vibe.

- **A code task:** implement a UK exclusion-referral form validator (required fields, a real UK postcode check, pupil age 4 to 18 as of a fixed date, an urgency enum). Graded by a hidden 14-case suite.
- **A reasoning task:** an LLM-cost problem with a deliberate trap, a model whose per-token rate is cheapest but which needs twice the output tokens, so it is not actually cheapest. One exact numeric answer.

Every run's token usage and cost came straight from the JSON, so nothing is estimated. The reasoning task has a fixed five-line answer, which makes its output-token count an almost clean read of thinking effort.

Numbers, on the clean warm-cache reasoning task:

| effort | quality | output tokens | cost (USD) | latency |
|--------|---------|---------------|------------|---------|
| high   | 5/5     | 362           | 0.0866     | 9.02s   |
| medium | 5/5     | 349           | 0.0863     | 7.08s   |
| low    | 5/5     | 300           | 0.0851     | 5.08s   |

The code task scored 14/14 at every level.

## Why it was worth doing

Three findings held up. Quality was flat: both tasks scored perfect at every effort level, so high effort bought zero extra correctness, including on the trap that low effort got right. Latency is the real signal: low is about 44% faster than high, and the gradient is monotonic. Cost barely moved: a 1.8% spread from low to high, because each run is dominated by a roughly 30k-token fixed input and cache footprint, the harness and system prompt, not by the handful of reasoning tokens effort adds.

That reframes the setting. On short, well-specified work turning the dial down buys speed, not a lower bill. The money saving only shows up when high effort would otherwise generate large reasoning-token counts, on genuinely long or ambiguous work. So it is a latency dial for bounded tasks and a cost dial for open-ended ones.

Per-task-type default we landed on: low for mechanical deterministic work, medium for well-specified code (margin for edge cases at ~20% lower latency than high), keep high for ambiguous or long-horizon reasoning.

## What's still off

This is one sample per cell. The output-token deltas are small and could sit inside run-to-run variance, so we lean on the two robust findings: quality did not degrade at low, and the latency gradient is real. The prompt cache has a five-minute time to live, which muddied cross-run cost until we isolated the warm reasoning task. Both tasks were bounded on purpose. None of this extends to open-ended work, which is exactly where we still expect effort to earn its keep on cost. That is the next measurement.
