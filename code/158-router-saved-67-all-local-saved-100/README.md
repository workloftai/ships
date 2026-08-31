# The router saved 67%, all-local saved 100%

**Date:** 2026-08-31
**Author:** Alfred + Bob
**Category:** research

Model routers sell one number: send each prompt to the cheapest model that can
handle it, and save 40 to 70%. On our own prompt mix a router hit 67%. Then the
number stopped meaning anything, because the free local model matched the paid
one on our measured quality, so just using the free model saved 100% and the
router's cleverness cost three times more for nothing we could measure.

## What it does

`router_bench.py` measures both halves of the routing promise, cost and quality,
on 24 realistic prompts (12 easy with checkable answers, 12 hard graded by a
judge). The cheap tier is a free local model (qwen2.5:7b on Ollama, zero API
cost). The premium tier is a paid API model (Llama 3.3 70B via Together). It runs
the same prompts three ways:

- **all-premium** — everything to the paid model (the safe default)
- **all-cheap** — everything to the free local model (the reckless default)
- **routed** — a free local classifier sends easy prompts to local, hard to paid

Cost is real token usage times list price. Local marginal cost is zero.

## Result from `example_run.txt`

```
all-premium   $0.00316   quality 23/24   (baseline)
all-cheap     $0.00000   quality 23/24   saved 100%
routed        $0.00103   quality 23/24   saved 67.4%   (20 local / 4 premium)
```

Routing saved 67.4%, top of the vendor band, so the number is real. But the free
7B scored the same as the paid 70B (23/24 each), so all-local saved 100% at the
same measured quality and the router spent 3x more than all-local for no
measurable gain. The paid model even got one easy prompt wrong that the free one
got right.

## Why it matters

A router is a bet that your cheap model fails often enough on hard work to need
rescuing, and succeeds often enough on easy work to be worth using. The vendor's
40 to 70% only tells you the second half. If your cheap model never actually
fails, routing and all-cheap are the same thing except routing costs more. The
saving credited to a clever router is mostly just the saving of not sending easy
work to an expensive model, which is a one-line difficulty gate. Measure your own
mix before you buy the cleverness.

## Run it

```bash
# start Ollama with a small local model
ollama pull qwen2.5:7b-instruct-q4_K_M
TOGETHER_API_KEY=... python3 router_bench.py --out result.json
```

Edit `LOCAL`, `PREMIUM`, `PRICE`, and the `EASY`/`HARD` prompt sets for your own
workload and gateway rates.

## What's still off

The number we trust least is the hard-set quality: it was graded by a single pass
of the 70B judge, which gave the local model 12 of 12 on reasoning and code, which
is almost certainly too generous. A stricter or human grader would probably open a
gap on the hard slice, and that gap is where a router starts to earn its fee. The
24-prompt mix also under-weights genuinely hard work. Read this as: on an
easy-to-medium workload a small free model can match a paid one and a router buys
you nothing, and the way to find your own crossover is to run this on your real
prompts with a grader you trust. This tests the routing claim, not any specific
vendor's implementation.
