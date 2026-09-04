# flash-coding-bench

Is a cheap frontier model actually cheap for coding? A deterministic, no-judge
benchmark that prices [Gemini 3.8 Flash](https://deepmind.google/) against a paid
open 70B and a free local model on the boring, high-volume coding work you would
hand a cheap subagent tier.

## The finding

On easy-to-medium coding tasks, all three tiers passed the same 8 of 8. Quality
did not separate them. Cost and latency did, and the "cheap frontier" model came
last on both:

```
tier                 pass    cost $     total tokens   time
Gemini 3.8 Flash     8/8     0.003276   1324           39s
Llama 3.3 70B        8/8     0.001365   1551           13s
qwen2.5:7b (local)   pass    0.00       free, but ~2 min/task on a CPU box
```

Gemini 3.8 Flash cost **2.4x more** than the paid open 70B (Llama 3.3 70B on
Together) and ran **3x slower**, at identical measured quality. The cause is the
price sheet, not the model: Flash is cheap on input (reported $0.75 / 1M) but
expensive on output ($3.75 / 1M), and short coding answers are output-weighted, so
the output price dominates the bill. A flat-priced commodity 70B undercut the cheap
frontier model on the exact work it is sold for.

## Why deterministic grading

Most model bench grade with an LLM judge, which introduces grader bias (our own
[router bench](https://workloft.ai/ships/router-saved-67-all-local-saved-100-2026-08-31.html)
had exactly that caveat). Here each task asks for a Python function with a fixed
signature; the harness extracts the code and runs it against hidden unit tests in a
subprocess. Pass means every assertion passed. The quality number is a pass rate
with no model in the loop.

## Run it

```bash
python3 flash_bench.py                    # all three tiers
python3 flash_bench.py --tiers flash,paid # skip the slow local tier
```

Keys: `GOOGLE_API_KEY` (Gemini), `TOGETHER_API_KEY` (Llama), Ollama on
`localhost:11434` (local). Edit the `PRICES` table at the top with your own
contract rates; the harness computes cost from real token counts.

## What's still off

- **Task difficulty is the load-bearing caveat.** These 8 tasks are easy-to-medium
  and everything passed, so this measures cost and latency on routine work, not hard
  reasoning. Genuinely hard problems are where a frontier model would open a quality
  gap and earn its output price. Do not read this as "Flash is worse", read it as
  "on routine coding, Flash's price advantage disappears".
- **Prices are as-reported**, not contracts we have billed against. The harness
  prints real token counts so you can plug your own rate.
- **N is 8, single-pass.**
- The local tier passes on quality but runs at roughly two minutes per task on a
  CPU box; it is free, but not a real-time coding tier without a GPU.

MIT. Steal what you want.
