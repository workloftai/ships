# A frontier model earns its price only when the task is hard

Ship 169, 5 September 2026. Companion code for the Workloft Ships article
[A frontier model earns its price only when the task is hard](https://workloft.ai/ships/frontier-model-earns-its-price-only-when-hard-2026-09-05.html).

We measured whether an expensive frontier model (GPT-6 Astra, priced at twice
our workhorse on output) is worth it for the work an agent fleet actually does,
then wired it in as an escalation lane rather than a default.

## The finding

Cost-per-solved-task, deterministic grading, answer keys computed by code (no
judge model in the loop):

```
EVERYDAY set        pass    cost / solved   out tokens   latency
Claude Opus 4.8     10/10   $0.00258        810          1.89s
GPT-6 Astra         10/10   $0.00337        511          2.40s

HARD set            pass    cost / solved   out tokens   latency
Claude Opus 4.8     12/12*  $0.0184         5634         6.17s
GPT-6 Astra         12/12   $0.0195         2472         5.05s
```

Both models pass on quality (the one Opus miss was a token-budget truncation of
a verbose method, not a wrong answer). What moves is cost, and it moves with
difficulty. On everyday work Astra costs about 31% more per solved task and runs
slower. On the hard set that gap collapses to about 6% and Astra becomes faster,
because its token efficiency grows with difficulty (37% fewer output tokens on
easy, 56% fewer on hard). The frontier premium only starts paying off as the work
gets hard. That crossover is the whole argument for a cascade instead of picking
one model.

## What's here

| File | What it is |
|------|------------|
| `run_eval.py` | The cost-per-solved-task harness. Runs a golden set through a model via OpenRouter (or direct Anthropic), grades deterministically, prints cost/tokens/latency and cost-per-solved-task. |
| `generate_v2.py` | Builds the hard golden set with every answer key computed by a reference implementation (so the key is provably correct). |
| `golden_set.json`, `golden_set_v2.json` | The everyday and frontier task sets. |
| `classifier.py` | Base keyword tier router plus the Astra spike-band detector. |
| `escalation.py` | The cascade policy: spike-band, repeated-tool-failure and low-confidence triggers to the frontier tier, plus a confirmation gate for write-access tasks. |
| `cache.py` | A semantic response cache (exact plus near-duplicate cosine match) with a pluggable embedder, to skip repeat calls entirely. |
| `result.json`, `example_run.txt` | The numbers above and a captured self-test run. |

## Run it

```bash
# self-tests, no keys needed
python3 escalation.py
python3 cache.py

# the eval (needs an OpenRouter key, and an Anthropic key for the Opus arm)
export OPENROUTER_TIER3_KEY=sk-or-...
python3 run_eval.py openai/gpt-6-astra OPENROUTER_TIER3_KEY astra
export ANTHROPIC_API_KEY=sk-ant-...
python3 run_eval.py claude-opus-4-8 ANTHROPIC_API_KEY opus48

# the hard set
python3 generate_v2.py
GOLDEN_SET=golden_set_v2.json python3 run_eval.py openai/gpt-6-astra OPENROUTER_TIER3_KEY astra_v2
```

## How we wired it in

Astra sits as a fourth tier above the cheap, workhorse and complex tiers. It is
invoked only on an escalation trigger: the task is in its proven spike band
(browser and computer use, cyber and vulnerability work, frontier maths, very
large context), or a cheaper tier failed tool calls twice, or the lower tier
self-reported low confidence. Escalations are capped per conversation, the key
carries a hard monthly spend cap, and any Astra task that can write (shell,
files, browser, deploy, payment) hits a confirmation gate before it runs.

## Caveats

Both sets are text-in, text-out and deterministically graded. Genuinely agentic
work (long-horizon browser and computer use) and true million-token context are
where a frontier model should pull away, and we cannot grade those without a live
tool and browser harness yet. N is small (10 and 12 tasks, single pass). The
escalation thresholds are sensible defaults, not yet tuned on production traffic.
Point the harness at your own tasks and your own contract prices.

Steal what you like.
