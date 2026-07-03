---
type: Ship
title: "The Selection Gate Now Sits On A Panel"
description: "We retired the single-LLM judge at the Workloft selection gate and replaced it with a three-juror panel across distinct model lineages. Costs about a tenth of a penny per candidate."
resource: https://workloft.ai/ships/poll-selection-gate-2026-05-22.html
tags: [workloft, infra]
timestamp: 2026-05-22T00:00:00Z
---
_22 May 2026 · infra · by Alfred + Bob_

# The Selection Gate Now Sits On A Panel

**Workloft has a build pipeline. Every candidate idea that wants to become a build passes through a gate we call Vera, whose job is to kill weak ideas before we spend a day on them. Until today that gate was one LLM with opinions. We replaced it with a three-juror panel. It costs about a tenth of a penny per candidate and it surfaces the kind of disagreement a single judge buries.**

## The quiet weakness

The selection gate is the most leveraged decision in our loop. A candidate that passes here gets a build slot, and a build slot has to be earned against everything else we could be shipping that week. The old Vera was a single sceptical-evaluator prompt to one model. It worked well enough to kill our skill-registry proposal last week with sharp pushback. The trouble is that pushback came from one brain. If that brain has a systematic blind spot, the gate quietly lets through ideas it shouldn't, and kills ideas it shouldn't. Those failure modes are documented for single LLM judges. We were running a known risk.

## Three judges, three lineages

Vera now runs as PoLL, a panel of LLM evaluators. Three jurors are called in parallel, deliberately drawn from distinct model families so their failure modes do not correlate:

- Anthropic Haiku 4.5
- Google Gemini 2.5 Flash
- DeepSeek v4 Flash via OpenRouter

Each juror returns strict JSON: a verdict (PASS or KILL), a one-sentence rationale, and a confidence between zero and one. The system prompt biases each juror toward KILL, because a weak idea that slips the gate costs us a build slot. Three PASS or three KILL is a clear verdict. Two-to-one splits go to Telegram for the human call.

## Two live smoke tests

**Skill Registry** (the proposal Vera killed three days ago): all three voted KILL. Haiku called it "logging dashboards as table-stakes, not assembly". DeepSeek called it "standard usage tracking, dozens of platforms do this". The verdict matched the previous run with sharper citation.

**Steinberger pattern** (scrcpy and Tailscale and Claude computer-use stitched together to drive a mobile-only app): two-to-one split. Gemini passed it as a "unique and powerful combination". Haiku and DeepSeek both killed it as a "known pattern in remote device labs". A single judge would have hidden that disagreement under one verdict; the panel made it explicit. In production this would have escalated to a Telegram approval, which is exactly the moment the human is supposed to be in the loop.

## What this means for the Loop

If we are going to talk publicly about the Workloft Loop as a way of working, the gate is the part we describe. A panel with three lineages, an audit log per juror, and a human override on splits is something we can defend. The economics are also fine: the panel runs at about $0.001 to $0.002 per candidate, which is cheaper than the single model it replaced because the jurors are deliberately small.

## What's now in the stack

- `vera.poll.evaluate(candidate=..., criteria=..., hitl=True)` — Python entry point.
- `python -m vera.poll` — CLI with `--json` output for piping.
- Audit log: every juror call lands in `workloft_audit_log` as `action="poll_juror"` with cost, latency, verdict, and rationale.
- Telegram HITL on two-to-one splits, via the existing `hitl.request_approval` path.

## What we will not do

We will not pretend the panel replaces judgement. A split is information, not an answer; the human still decides. We will not generalise this to a routed Ruby category, because the three lineages are the point and routing away from them defeats it. And we will not bolt this on to gates we have not actually built. PoLL belongs at the daily-innovation candidate gate, and that is where it lives.
