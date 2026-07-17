# deepfix

Repair an agent's reasoning, then distil the repair into a reusable rule.

Most agent fixes are thrown away. The model reasons its way into the same wrong
turn tomorrow that it took today, so the operator pastes the same correction into
context again, and again, growing the prompt every time. `deepfix` does the
opposite. You edit the one reasoning step that went wrong, then distil that edit
into a short directive that prevents the whole class of error on future runs, for
a fraction of the tokens.

This is a small, honest implementation of the idea in _Deep Interaction: An
Efficient Human-AI Interaction Method for Large Reasoning Models_
([arXiv:2607.14049](https://arxiv.org/abs/2607.14049)): correct the chain of
thought directly, then carry the correction as a distilled prompt rather than a
re-run.

## Four verbs

```
deepfix edit    trace.json --step 2 --to "the corrected reasoning"
deepfix distil  trace.json --out directives.json --llm
deepfix apply   "the next task" --directives directives.json
deepfix cost    trace.json --directives directives.json --runs 100
```

- **edit** records a human rewrite of one reasoning step of a captured trace.
- **distil** turns that correction into a compact, reusable directive. This is
  the step that needs a model: compression is the model's job. Without `--llm`
  it stores the correction verbatim and is honest that nothing was compressed.
- **apply** composes the next run's prompt with accumulated directives prepended.
- **cost** compares carrying the fix inline on every run against injecting the
  distilled directive.

## Run the demo

```bash
python3 demo.py          # offline, deterministic, no model, no network
python3 demo.py --llm    # real distillation via Claude (needs ANTHROPIC_API_KEY)
```

The offline run proves the mechanism but not the saving: with no model the
directive is the full correction, so it saves nothing. The tool says so out loud.
Bring a model and the rule compresses.

## What we measured

Real numbers from `demo.py --llm`, counted with `tiktoken` (`cl100k_base`):

| correction carried inline | tokens/run | distilled directive | tokens/run | saved/run | over 100 runs |
|---|---|---|---|---|---|
| short one-line fix (39 chars-worth) | 39 | a rule | 25 | 36% | 1,400 |
| realistic worked correction | 114 | a rule | 25 | 78% | 8,900 |

The directive stays about 25 tokens no matter how long the original correction
was. So the longer and more careful your inline re-teaching, the more the
distilled version saves, and it saves it on every run for the life of the agent.

## Keys

`distil --llm` reads `ANTHROPIC_API_KEY` from the environment, or from
`~/larry-tier-routing/.env.tier-keys` if present. Default model is
`claude-haiku-4-5-20251001`; override with `--model`.

## Tests

```bash
python3 test_deepfix.py           # no pytest needed
python3 -m pytest test_deepfix.py -q
```

Offline only: no network, no model calls.

## What's still off

- Distillation quality is the model's; a lazy model writes a lazy rule. Read the
  directive before you trust it.
- Directives accumulate. Nothing here dedupes or retires a stale one yet; that is
  the obvious next piece.
- Token counting falls back to a characters/4 estimate when `tiktoken` is not
  installed. The tool flags when it is estimating.
