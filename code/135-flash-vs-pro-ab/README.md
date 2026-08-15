# flash-vs-pro-ab — measure "cheaper AND better" before you believe it

Gemini 3.7 Flash shipped on 13 August 2026, cheap and coding-tuned. We route our
agent fleet's code and reasoning work to the pricier Gemini 2.5 Pro, so we ran
them head to head before swapping anything.

The flash model won on every axis:

| | gemini-3.7-flash | gemini-2.5-pro |
|---|---|---|
| Accuracy | **12/12** | 10/12 |
| Cost / 1k tasks | **$1.36** | $10.48 |
| Avg latency | **2.03s** | 7.30s |
| Total thinking tokens | 2,769 | 11,333 |

87% cheaper, more accurate, 3.6x faster, a quarter of the thinking burn.

## The interesting part

The pro model's two misses weren't bad reasoning. Both models had the same
2048-token budget. Gemini 2.5 Pro spent so much of it on hidden *thinking* that
on two tasks it ran out before writing an answer and returned an empty string.
Gemini 3.7 Flash reached the same answers with far fewer thinking tokens, so it
never hit the wall.

That's the reason the bench measures `thoughtsTokenCount`, not just output. A
model's headline price is a floor. What you actually pay is that price times how
many tokens it decides to think for, and a heavy reasoner on an easy question is
the worst of both: you pay for the thinking and sometimes don't even get an
answer.

## Run it

```bash
GOOGLE_API_KEY=... python3 bench.py
```

Twelve tasks with a single checkable answer each (Fibonacci, unit conversion, a
syllogism, binary conversion, popcount, a sequence, a distinct-sum). Temperature
0, a fixed token budget for both, real token counts, cost off each model's rate
card with thinking billed as output. `result.json` is our run.

## The caveat we shipped with

The winner has the loser's weakness. Gemini 3.7 Flash is also a thinking model,
so on a tight token budget it too spends the lot on thinking and returns nothing
(we checked: 50 tokens gives an empty string, 300 gives the right answer). So it
belongs only on routes that run with room to think. We scoped it to the code and
reasoning tiers and left the tight, high-volume classify/extract calls on the
non-thinking flash model. Adopting a thinking model everywhere its price tag
allows quietly reintroduces the empty-answer bug on your cheapest calls.

Twelve medium tasks with single-value answers is enough to prefer one model over
another on a route, not to rebuild a tier. We didn't test hard agent loops,
vision, or long context. The intro pricing expires end of 2026.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
