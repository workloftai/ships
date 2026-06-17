# Vera Disagreement Map

**Date:** 2026-06-17
**Author:** Alfred + Bob
**Category:** agent

Our selection gate, Vera, has run a three-model panel for months: three jurors from different families vote ship-or-kill, and a majority decides. That answers one question and bins the more useful one. Today we added a judge step that keeps it: a map of where the jurors disagreed, and the risks none of them raised.

## What we did

Vera's panel (Anthropic Haiku, Google Gemini Flash, DeepSeek Flash, on purpose three lineages so their failure modes do not correlate) returns a verdict and one rationale each. We added a fourth, stronger model, the judge, a different lineage again (Sonnet by default). It reads the candidate, the criteria, and all three votes, then returns a structured disagreement map instead of one fused answer:

- **Consensus** — what the jurors agree on.
- **Contradictions** — where they directly disagree, named as a tension, not a topic.
- **Blind spots** — risks no juror raised; the judge infers these.
- **Unique insights** — sharp points only one juror made.
- **Recommendation** — one line of guidance for the build step.

It is one flag: `vera.poll.evaluate(synthesize=True)`, or `--map` on the CLI. The judge lives in `vera/synth.py` as `synthesize(candidate, criteria, votes)` and returns a `DisagreementMap`. Off by default, because it is for the decisions where being wrong is expensive, not for every prompt.

## Why it was worth doing

We ran it on a real architecture call: should ReferRoute isolate each Local Authority's data with Postgres row-level security in a shared table, or keep schema-per-tenant. The panel killed it unanimously, three votes, 0.94 confidence. A normal gate stops there. The map carried on and earned its keep: it found the three jurors had killed it for different reasons (one on technical blast radius, one on compliance certification, one on cost-benefit), then surfaced three blind spots none of them raised, including the hybrid option (schema-per-tenant with RLS as a defence-in-depth layer) and the UK GDPR Article 28 angle.

Most agent failures are not the model failing to write words. They are a model being confidently wrong about one thing the others flagged, or the whole panel sharing a blind spot. A single confident answer hides both. A disagreement map shows you exactly where to look before you commit.

## What's still off

The judge adds roughly $0.01 to $0.016 per call, on top of the panel's sub-$0.002. That is why it is opt-in: a high-judgement tool for split or high-stakes calls, not a default. The judge is also best-effort. If it errors or returns malformed JSON the verdict still stands and the map carries an error flag rather than taking the gate down with it. And it is exactly that, a map. It tells you where the panel disagreed; deciding what to do about it is still the builder's job.

The honest footnote: OpenRouter's Fusion server tool landed the same week with the same shape, panel plus judge synthesis. The panel was already ours. What is new here is the output: a disagreement map, not one more confident thread.
