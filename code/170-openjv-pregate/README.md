# 170 · OpenJV pre-gate: read the verdict off the logits

A local, zero-cost "system-1" tier for an LLM quality gate. Frame a typed
decision (here KILL vs PASS) as a one-word answer, run a **frozen small model
for a single forward pass**, and read the probability it puts on each option
token straight off the logprobs. No generation, no fine-tuning, no cloud call.
The confidence is the model's own answer-token probability, normalised over the
two options.

This is the open reproduction of the "type-safe decision model" interface: you
do not need a new closed model or its API to get a calibrated typed decision.
Any small instruct model that exposes token logprobs already does it. Here the
frozen model is `gemma3:4b` served by Ollama; nothing depends on a GPU, only on
an endpoint that returns `top_logprobs`.

## The one design decision that matters

The pre-gate reads both probabilities but **only acts on a confident KILL**. A
confident PASS is recorded and then ignored: the case still falls through to
the paid tiers behind it. That asymmetry is the whole safety story. A cheap KILL
is free money; a cheap PASS is the vibe trap. So the free model is allowed to
stop the line, never to bless it. The worst it can do is save a call you did not
need to make. It can never add a wrong yes.

Where it sits in a selective-verification ladder:

```
precheck  (deterministic rules)                 $0
   -> openjv pre-gate  (local, one forward pass) $0   <-- this
   -> screen  (one cloud juror)                  ~$
   -> panel   (three cloud jurors)               ~3x
```

## How it works

- Build a strict prompt: criteria + output, answer with exactly one word.
- Generate one token with `logprobs` on; read the top candidates.
- Sum probability mass over KILL-shaped and PASS-shaped tokens (so ` KILL`,
  `Kill`, `KILL` fold together), normalise against each other -> `P(KILL)`.
- Fire the short-circuit only when `P(KILL)` clears a threshold; else abstain
  and fall through. A temperature knob calibrates against your labels.

It **never raises**: a dead endpoint or malformed response returns `ABSTAIN`
with cost 0, so the fall-through path is always safe. Ship it behind a flag
(`VERA_OPENJV_PREGATE`, default off), prove the false-KILL rate on your own
labels, then flip it.

## Run it

```
python3 demo.py                        # decides five cases at $0, no cloud
python3 -m unittest -v test_openjv     # 7 tests, no Ollama needed
```

`demo.py` needs an Ollama endpoint with a small model pulled
(`ollama pull gemma3:4b`, or set `VERA_OPENJV_MODEL`). The tests do not.

## Config (env)

| var | default | meaning |
|---|---|---|
| `VERA_OPENJV_PREGATE` | `0` | `1` to enable the short-circuit in your ladder |
| `VERA_OPENJV_MODEL` | `gemma3:4b-it-q4_K_M` | Ollama model tag |
| `VERA_OPENJV_CONF` | `0.85` | min `P(KILL)` to fire |
| `VERA_OPENJV_TEMP` | `1.0` | temperature-scaling factor for calibration |
| `VERA_OPENJV_URL` | `http://localhost:11434` | Ollama base URL |
| `VERA_OPENJV_MAXCHARS` | `6000` | candidate truncation before the pass |

## Honest limits

- Coverage of a decision is not comprehension. This catches confident wrong
  answers cheaply; it does not reason.
- On a memory-starved box a multi-GB model cannot stay resident and each pass
  reads weights off disk (slow). The technique is `$0` and correct regardless;
  it is *fast* only on iron that holds the model in memory. Best as an offline
  batch tier, or on a GPU.
- Calibration is model- and task-specific. Fit `VERA_OPENJV_TEMP` against your
  own labelled set before trusting the confidence.

MIT licensed. Part of [Workloft Ships](https://workloft.ai/ships).
