# flash-coding-bench

Is a cheap frontier model actually cheap for coding? A deterministic, no-judge
benchmark that prices [Gemini 3.8 Flash](https://deepmind.google/) against a paid
open 70B and a free local model on the boring, high-volume coding work you would
hand a cheap subagent tier.

## The finding

On easy-to-medium coding tasks, all three cloud tiers passed the same 8 of 8. Quality
did not separate them. Cost did, and the "cheap frontier" model came last:

```
tier                 pass    cost $     total tokens   time
Llama 3.3 70B        8/8     0.001365   1551           13s
Gemini 3.8 Flash     8/8     0.003276   1324           39s
Claude Opus 4.8      8/8     0.031905   1949           18s
qwen2.5:7b (local)   1/8     0.000000   free, but timed out on 7/8 on CPU
```

The three cloud tiers passed 8 of 8 across a **23x cost spread**. Gemini 3.8 Flash cost
**2.4x more** than the paid open 70B (Llama 3.3 70B on Together) and ran **3x
slower**; Claude Opus 4.8 cost **23x the 70B** and ~10x Flash and got the same eight
answers right. On this workload the entire cloud price ladder bought nothing measurable.
The free local model (qwen2.5:7b) was not viable on a CPU box: it timed out on 7 of 8
tasks (a 5-minute per-call limit, three retries each), completing only one.
Flash losing to the 70B is the price sheet, not the model: it is cheap on input
(reported $0.75 / 1M) but expensive on output ($3.75 / 1M), and short coding answers
are output-weighted, so the output price dominates the bill. Frontier models earn
their price on hard problems, which this bench does not test — so spend the tier on
task difficulty, not on routine high-volume work a cheap tier does just as well.

## Why deterministic grading

Most model bench grade with an LLM judge, which introduces grader bias (our own
[router bench](https://workloft.ai/ships/router-saved-67-all-local-saved-100-2026-08-31.html)
had exactly that caveat). Here each task asks for a Python function with a fixed
signature; the harness extracts the code and runs it against hidden unit tests in a
subprocess. Pass means every assertion passed. The quality number is a pass rate
with no model in the loop.

## Run it

```bash
python3 flash_bench.py --tiers flash,paid,opus  # the cloud comparison
python3 flash_bench.py --tiers local            # local only (slow on CPU)
```

Keys: `GOOGLE_API_KEY` (Gemini), `TOGETHER_API_KEY` (Llama), `ANTHROPIC_API_KEY`
(Opus), Ollama on `localhost:11434` (local). Edit the `PRICES` table at the top with
your own contract rates; the harness computes cost from real token counts.

## What's still off

- **Task difficulty is the load-bearing caveat.** These 8 tasks are easy-to-medium
  and every cloud tier passed, so this measures cost and latency on routine work, not
  hard reasoning. Genuinely hard problems are where a frontier model would open a
  quality gap and earn its output price. Do not read this as "Flash is worse", read it
  as "on routine coding, Flash's price advantage disappears".
- **Prices are as-reported**, not contracts we have billed against. The harness
  prints real token counts so you can plug your own rate.
- **N is 8, single-pass.**
- **The local tier is CPU-bound and not viable here.** qwen2.5:7b timed out on 7 of 8
  tasks under a 5-minute per-call limit; only one finished (and passed). It is free,
  but you need a GPU for it to be a real tier. (An earlier partial run passed 3/3 and
  misled us into "it passes" briefly; the full run corrected that.)

MIT. Steal what you want.
