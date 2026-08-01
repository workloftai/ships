# v4-flash reasoning-swap

A provider can change a model's *character* without changing its id or its price.
On 2026-07-31 DeepSeek shipped an "enhanced agent" v4-flash that is now a
reasoning-by-default model, served under the same `deepseek/deepseek-v4-flash`
id it had before. Our router kept pointing at the same string and silently
inherited the new behaviour.

Where that bites: a cheap mechanical tier (classify, extract, short labels) runs
with a deliberately tight `max_tokens`, because the answers are one or two tokens.
A reasoning model spends that budget on hidden reasoning first, so under a tight
cap it returns `content: null` before writing any answer.

## Reproduction

Same prompt, same `max_tokens: 20`:

| call | content | reasoning tokens |
|---|---|---|
| default (reasoning on) | `null` | 20 |
| `reasoning: {enabled: false}` | `"Yes"` | 0 |

## The honest measurement

`bench_reasoning_swap.py` runs a 10-task mechanical suite at temp 0. With
`max_tokens: 512` (headroom), the reasoning model still scored 10/10 and stayed
the cheapest option ($0.013 / 1k tasks vs a non-reasoning sibling's $0.016). So
the upgrade did not ruin accuracy or cost. What it added was variance: reasoning
fired on 3 of 10 trivial tasks, non-deterministically even at temp 0, and ran
67% slower. Under a tight mechanical budget that variance is a null reply on
roughly one call in three.

## The fix

Send `reasoning: {enabled: false}` on mechanical calls to reasoning-capable
models. The unified `reasoning` param is OpenRouter-wide; only send it to models
that support reasoning (others 400 on it). Answers become deterministic, instant,
and 0 reasoning tokens.

## Run it

```bash
export OPENROUTER_API_KEY=sk-or-...
python3 bench_reasoning_swap.py
```

The lesson: pin the behaviour you depend on, not just the model id.
