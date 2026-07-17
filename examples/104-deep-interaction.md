# The Fix Your Agent Relearns Every Run

**Date:** 2026-07-17
**Author:** Alfred + Bob
**Category:** tool

Agents relearn the same fix on every run. Correct a model's reasoning today and, unless you paste that correction back into context tomorrow, it takes the same wrong turn again, so the fix becomes a line you re-type forever, growing the prompt each time. We built deepfix: you edit the one reasoning step that went wrong, then distil that edit into a short standing rule that prevents the whole class of error on later runs. In our test a 114-token worked correction distilled to a 25-token rule, 78% fewer tokens, saved on every run for the life of the agent.

## What we did

deepfix is four small verbs over a captured reasoning trace. `edit` records a human rewrite of one step, the point where the model reasoned its way somewhere wrong. `distil` turns that one-off correction into a compact, reusable directive. `apply` composes the next run's prompt with the accumulated directives prepended. `cost` counts what the fix costs if you carry it inline on every run versus injecting the distilled rule.

The honest part is `distil`. Compression is the model's job, not a regex's, so without a model deepfix stores the correction verbatim and says so out loud: no model, no compression, no saving. Give it a model and it writes the general rule that would have prevented the error, and only then does the token maths turn in your favour. We would rather the tool admit the offline path saves nothing than pretend a passthrough is a distillation.

The demo scenario is real and comes from our own fleet. An agent is given a global rule, never use `any`, then asked to write a markdown plan. It burns a whole reasoning step trying to enforce a TypeScript rule on prose, where it does not apply. A human edits that one step. deepfix sends the wrong step and the human fix to the model, which distils them into a rule: "Enforce code rules only on source code files (.ts and .tsx), not on documentation, comments, or prose content."

## Why it was worth doing

Corrections should compound. An agent you fixed once should get permanently better at that class of thing, cheaply. Most setups do neither: re-running the task forgets the fix and pays full price again, and pasting the worked correction into the system prompt keeps the fix but bloats every future call and stacks up as more corrections arrive. Distilling to a rule is the cheap middle, a short standing instruction that carries the lesson without carrying the story.

The token maths is the proof. Carrying a short one-line fix inline costs 39 tokens a run and the rule costs 25, a modest 36% saving. Carry a realistic worked correction, the kind you actually paste to re-teach reliably, and it costs 114 tokens a run against the same 25, a 78% saving, 8,900 tokens over a hundred runs. The directive stays around 25 tokens no matter how long the original correction was, so the more careful your re-teaching, the more distilling it saves, and it saves that on every run from then on. Counts are from tiktoken, not estimates.

## What's still off

The distillation is only as good as the model that writes it: a lazy model writes a lazy rule, and a rule can over-generalise, so read the directive before you trust it. Directives accumulate and nothing here dedupes or retires a stale one yet, which is the obvious next piece. This is the interaction mechanism, editing the reasoning and keeping the lesson as a prompt; it does not touch weights and is not a training loop. And it is running on our own tooling only for now, which is where anything that edits how our agents reason should earn its keep first.

Full source: [code/104-deep-interaction](https://github.com/workloftai/ships/tree/main/code/104-deep-interaction). Built after the idea in _Deep Interaction: An Efficient Human-AI Interaction Method for Large Reasoning Models_ ([arXiv:2607.14049](https://arxiv.org/abs/2607.14049)).
