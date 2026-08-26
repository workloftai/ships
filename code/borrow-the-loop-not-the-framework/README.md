# borrow the loop, not the framework

Companion code to Workloft Labs Note No. 76, [**We Rebuilt a Research Paper's Self-Tuning Loop in 110 Lines**](https://workloft.ai/labs/notes/borrow-the-loop-not-the-framework-2026-08-26.html).

Two papers this year ship the same good idea: let an agent tune its own prompts by diagnosing its own failures.

- FAPO, Cisco Foundation AI: https://arxiv.org/abs/2606.19605
- AutoSaddler: https://arxiv.org/abs/2608.23041

Both arrive wrapped in a framework (pipelines, an agent orchestrator, tenant scaffolding, optional Kubernetes and cloud storage). The idea underneath is small. This is the idea, on its own, in about 110 lines.

## The loop

```
evaluate a prompt on a dataset
  -> attribute the single dominant failure
  -> propose a targeted rewrite
  -> KEEP it only if it scores better
  -> repeat, bounded, stop at target
```

That is the whole engine. The part people skip is the fourth line: a change is kept only if a number went up. No "that reads better to me".

## Use

The loop in [`optimize.py`](./optimize.py) has no framework and no provider baked in. It needs one thing from you: a `chat_fn` that maps chat messages to text. Bring your own model, OpenAI or a local open-weight one, it does not care.

```bash
pip install openai
export OPENAI_API_KEY=sk-...
python3 demo.py
```

The demo hands the loop a deliberately bad, chatty system prompt scored on exact-match yes/no questions. A chatty answer fails. Expected shape:

```
[round 0] baseline score = 0
[round 1] diagnosis: The model provided full explanatory sentences instead of the single-word answers expected.
[round 1] candidate = "Answer with only 'yes' or 'no'. Do not provide any explanation or additional text."
[round 1] score = 100  (KEPT)
score trajectory: 0 -> 100
```

To run it against a local model, point the OpenAI client's `base_url` at any OpenAI-compatible endpoint and change the model name. Nothing else changes.

## The honest limits

- This is the **prompt** tier only, the first and highest-return escalation FAPO does. It does not touch model parameters or restructure the pipeline, which is where the papers report their biggest jumps on harder tasks.
- The demo dataset is a toy, chosen to make the mechanism legible in one screen.
- The loop is only ever as good as the dataset it optimises against and the scorer that decides what "better" means. A weak scorer optimises confidently towards the wrong thing.

None of that is a flaw in the method. It is the method telling you the real work is in the evaluation, not the optimiser.

## Licence

MIT. Steal what you want.
