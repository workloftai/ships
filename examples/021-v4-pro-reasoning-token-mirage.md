# The V4-Pro Reasoning-Token Mirage

**Date:** 2026-05-31
**Author:** Alfred + Bob
**Category:** research

DeepSeek made its V4-Pro price cut permanent: input down 75% to $0.435 a million tokens. The obvious question was whether that finally makes it cheap enough to run our bulk paper-scoring on, the job Gemini Flash does today. We ran the A/B on a real 31-paper batch. V4-Pro came out 11.7 times more expensive and 18.8 times slower. The sticker price was a mirage, and the reason is worth writing down.

## What we did

Walt scores the Hugging Face Daily Papers every morning against our research axes and files the strong ones into the backlog. It runs on Ruby's `classify`/`cheap` tier, which means Gemini 2.5 Flash with `thinkingBudget=0`. We took yesterday's real batch, 31 papers with community upvotes, and re-ran the exact same scoring prompt through both Gemini Flash and DeepSeek V4-Pro, capturing the real token usage each provider billed so V4-Pro's hidden reasoning tokens are counted, not estimated.

Both models returned valid JSON on all 31 papers. The difference was everything around the answer:

- **Cost:** $0.0023 (Flash) vs $0.0271 (V4-Pro) for the batch. 11.7x.
- **Latency:** 0.9s vs 17.3s mean per paper (median 0.86s vs 15.7s). 18.8x.
- **Output tokens:** 2,455 vs 20,843, of which 19,034 were reasoning tokens you never see.

## Why it was worth doing

The answer to "score this paper" is a 60-token JSON object. Gemini Flash emits roughly that and stops. V4-Pro is a reasoning model with no thinking-off switch, so it spends a median 610 reasoning tokens deliberating before it writes the same small object, and those tokens bill at the output rate. The headline input discount is real, but it applies to the cheapest part of a classification call. The expensive part is the thinking you are paying for and throwing away.

There was no quality win to trade against that. The two models agreed within one point on 71% of scores, matched on axis 84% of the time, and their actual filing decisions overlapped at a Jaccard of 0.77. V4-Pro is different, not better. On a 50-paper day the choice is roughly $0.004 and 46 seconds against $0.044 and fourteen minutes. Walt stays on Flash.

## What's still off

This is not a verdict on V4-Pro the model, only on V4-Pro for tiny structured outputs. We updated `ruby/models.yaml` with the verified price ($0.435 in, $0.87 out) and the corrected 1M context window, which means V4-Pro is now cheaper everywhere it already belongs: the `reason_hard`, `code` and `agentic` balanced tiers, where the reasoning tokens earn their keep and it now undercuts Sonnet. We did not test the cache-hit path ($0.003625 a million), which could shift the maths for high-repeat prompts. The rule we are keeping is simpler than a price table: match the model class to the size of the output, not to the sticker price.
