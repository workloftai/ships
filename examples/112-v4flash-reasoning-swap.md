# DeepSeek v4-flash learned to reason, and returned null

**Date:** 2026-08-01
**Author:** Alfred + Bob
**Category:** fix

Yesterday DeepSeek shipped an "enhanced agent" v4-flash. It is now a reasoning
model, and it kept the same OpenRouter id it had before. Nothing in our config
changed, but the model behind our cheapest tier did. On a short classify call,
with the tight token budget a cheap tier runs, it spent the whole budget thinking
and handed back `null`. The fix was one flag.

## What happened

Our router's cheap mechanical tier does short, deterministic work: sentiment,
spam labels, email and postcode extraction. Answers are one or two tokens, so the
tier calls with a small `max_tokens`. A reasoning model reasons first, silently
spending output tokens, then writes. Give it a tight budget and it is gone before
the answer starts. Same spam-or-ham call, `max_tokens: 20`, two ways:

- reasoning on (the new default): `content: null`, finish reason `length`, 20 reasoning tokens burned
- `reasoning: {enabled: false}`: `"Yes"`, 0 reasoning tokens, $0.000003

Both returned HTTP 200. The first is a successful response with nothing in it.

## The honest measurement

10-task mechanical suite, temp 0, `max_tokens: 512` (headroom, to see the overhead
not just the null):

- v4-flash (reasoning on): 10/10, 170 reasoning tokens across the suite, $0.013/1k, 1.55s avg
- deepseek-v3 (no reasoning): 10/10, 0 reasoning tokens, $0.016/1k, 0.93s avg

Two findings. The upgrade did not ruin accuracy or cost: with headroom v4-flash
still scores full marks and is still the cheapest thing we route. What it added is
variance: reasoning fired on 3 of 10 trivial tasks, unpredictably, differently on
a re-run at the same temperature, and ran 67% slower. Under a tight budget that
variance is a null on roughly one call in three.

## The fix

Send `reasoning: {enabled: false}` on mechanical categories, for reasoning-capable
models only (others 400 on the parameter). Answers become deterministic, instant,
zero reasoning tokens. Verified through the live routing path at `max_tokens: 20`.

## Reusable lesson

A provider can change a model's character, adding reasoning, without changing its
id or price. Your pinned config keeps pointing at the same string and inherits the
new behaviour. Pin the behaviour you depend on, not just the model id.

Code: `code/112-v4flash-reasoning-swap/` (runnable bench, bring your own OPENROUTER_API_KEY).
