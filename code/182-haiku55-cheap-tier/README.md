# 182 · Haiku 5.5 beat our cheap models on real work

Write-up: https://workloft.ai/ships/haiku-5-5-beat-our-cheap-models-2026-10-17.html

An A/B of Claude Haiku 5.5 against the cheap models our fleet already used, on two
real jobs with their production prompts and this week's real inputs.

| Job | Model | Quality | Cost |
|---|---|---|---|
| Scoring 141 items (0-10), vs Opus 5 reference | Gemini 2.5 Flash, thinking off | 1.34 pts off, shortlist F1 0.57 | $0.038 |
| | Haiku 5.5, effort low | 0.49 pts off, F1 0.50, 4/141 broken JSON | $0.021 |
| | Haiku 5.5, effort high | 0.49 pts off, F1 0.67 | $0.032 |
| Editing 3 shortlists, blind Opus 5 judge (/10) | DeepSeek V4 Pro | 6.3 overall, grounding 5.7 | $0.019 |
| | Haiku 5.5, effort low | 7.7, grounding 9.0 | $0.006 |
| | Haiku 5.5, effort high | 8.7, grounding 9.7 | $0.012 |

Costs are list prices, from each provider's returned token counts. Full numbers in
`result.json`.

## Run it on your own work

`bench.py` is the script as we ran it. It imports two of our internal modules (`ruby`
for API keys, `agentic_oddities` for the production prompts), so to reuse it:

1. Replace `walt_prompt()` and the `VERA_SYSTEM` prompt with your own prompts and inputs.
2. Replace `ruby._KEYS[...]` with your own keys.
3. Keep the shape: incumbent vs candidate at two effort levels, a stronger model as
   reference or blind judge, and cost from real usage, not from the price table.

Things we learned the hard way:

- `claude-haiku-5-5` returns 400 if you send `temperature`.
- At low effort it does not think; at high it does (adaptive). Size `max_tokens`
  for the thinking, not just the answer, or replies come back empty.
- Its tokeniser used about 50% more input tokens than Gemini on the same prompts.
  Check cost per task, not per token.
- OpenRouter has dropped `google/gemini-2.5-flash` (404); we called Google directly.

## What's still off

The reference and the judge are both Claude, so a family bias is possible. Small
samples: 7 shortlist items, 3 editing runs. Two jobs, not a whole fleet.
