# Vera-escalate auto-tier in Ruby

**Date:** 2026-06-03
**Author:** Alfred + Bob
**Category:** agent

Our router used to answer at whatever model tier you asked for and hand the result straight back. Now it grades its own answer first. Ruby runs the cheap model, puts the reply in front of a three-juror panel, and if the panel is not convinced it climbs the tier ladder by itself, retrying on a stronger model until the answer holds up. Cheap by default, expensive only when the work earns it.

## What we did

Ruby is our model router. Vera is our selection gate, a three-juror PoLL panel (Haiku, Gemini Flash, DeepSeek v4 Flash, three different model families on purpose) that votes PASS or KILL on a candidate. They used to be separate steps. We wired them together.

The new function is `ruby.chat_escalating(...)`. It runs the prompt at the cheap tier, hands the answer to Vera's panel to judge against a caller-supplied rubric, and then decides:

- Panel returns PASS at or above your confidence floor, the answer ships as is.
- Panel returns KILL, a 2:1 split, or a PASS below the floor, the job escalates one rung up the ladder (cheap, then balanced, then premium) and re-runs.
- The first answer that clears the panel wins.
- If the top tier still cannot satisfy the panel, you get the premium answer flagged `accepted=False`, so a weak result is labelled, never passed off as solid.

A split panel matters here. When the three jurors disagree, the panel runs without a human in the loop and returns the majority verdict with its confidence capped below the floor, which is exactly what trips the next rung. Disagreement escalates on its own. There is a `ruby escalate` CLI for it too.

## Why it was worth doing

Picking a model tier up front is a guess. Guess cheap and a hard prompt comes back thin. Guess premium and you pay Opus rates for questions Haiku could have answered. This flips it: start cheap, pay for the panel (a fraction of a penny, around $0.0005 a check in testing), and only spend on a bigger model when the cheap answer actually fails the bar. The router stops guessing and starts measuring.

It also closes a gap in the loop. Vera was already the gate that kills weak build candidates. Now that same panel guards live answers, so a shaky reply gets caught and upgraded instead of quietly returned.

## What's still off

The panel's judgement is only as good as the rubric you hand it. A vague criteria string gives you a vague PASS, so the caller still has to say what good looks like. Escalation also adds latency: a full climb from cheap to premium means three model calls plus three panel runs before you get an answer, so this is for work where being right beats being instant, not for hot paths. And the panel itself can be wrong, three small models can agree on a bad answer, so the confidence floor is a dial to tune per job, not a guarantee.
