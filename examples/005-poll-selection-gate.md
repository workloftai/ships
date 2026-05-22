# The Selection Gate Now Sits On A Panel

**Date:** 2026-05-22
**Author:** Alfred + Bob
**Category:** infra

Workloft has a build pipeline. Every candidate idea that wants to become a build passes through a gate we call Vera, whose job is to kill weak ideas before we spend a day on them. Until today that gate was one LLM with opinions. We replaced it with a three-juror panel. It costs about a tenth of a penny per candidate and it surfaces the kind of disagreement a single judge buries.

## What we did

Vera now runs as PoLL, a panel of LLM evaluators. Three jurors are called in parallel, deliberately drawn from distinct model families so their failure modes do not correlate:

- Anthropic Haiku 4.5
- Google Gemini 2.5 Flash
- DeepSeek v4 Flash via OpenRouter

Each juror returns strict JSON: a verdict (PASS or KILL), a one-sentence rationale, and a confidence between zero and one. The system prompt biases each juror toward KILL, because a weak idea that slips the gate costs us a build slot. Three PASS or three KILL is a clear verdict. Two-to-one splits go straight to Telegram for the human call.

We tested it live on two real candidates. The Skill Registry proposal, which the old single-judge Vera killed three days ago, drew three KILL votes again with sharper citations. The Steinberger pattern (scrcpy plus Tailscale plus Claude computer-use, stitched into a way for an agent to drive any mobile-only app) drew a two-to-one split that a single judge would have buried under one verdict. That is the kind of disagreement we want surfaced, not hidden.

## Why it was worth doing

The selection gate is the most leveraged decision in our loop. A candidate that passes here gets a build slot, and a build slot has to be earned against everything else we could be shipping that week. Single LLM judges have documented failure modes (rubric-induced preference drift, model-family blind spots, prompt-injection susceptibility) and those failure modes compound at the gate.

There is also a credibility argument. If we are going to talk publicly about how the Workloft Loop runs, the gate is the part we describe. A panel with three lineages, an audit log per juror, and a human override on splits is something we can defend. The economics happen to also work: the panel runs at about $0.001 to $0.002 per candidate, which is cheaper than the single model it replaced because the jurors are deliberately small.

## What's still off

The panel is hardcoded as those three jurors. That is by design (three lineages is the point) and we do not want to route this through Ruby's normal category-based selection, but it does mean that if one provider is down, we run with two voters and a degraded confidence score. Today's smoke test caught Gemini Flash mid-503, and the panel coped, but we have not added a retry-with-sibling fallback yet.

The other thing we have not done is calibrate the criteria text against Alfred's actual taste. PoLL killed the Steinberger pattern as "known assembly" by a two-to-one margin. That is defensible reasoning, but it is also a useful test of whether the criteria text matches the bar Alfred actually applies. Calibration is a tuning step, not a panel problem.
