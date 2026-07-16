# Judge Allowlist Drift

**Date:** 2026-07-16
**Author:** Alfred + Bob
**Category:** fix

One of our nightly evals started failing correct work. The pass-rate on "did the agent invoke the right skill" dropped from 100% to 20% overnight, and the eval fired a regression alert. The agent had done nothing wrong. The judge had. Its hard-coded list of valid skills had gone stale, so it was flagging real skill invocations as made-up ones.

## What we did

Vera is our standing eval. Every night it samples what our agents actually did, scores each output with a three-model judge panel (a PoLL: Panel of LLM Evaluators, one Anthropic, one Google, one DeepSeek juror so their blind spots do not correlate), and pings us only on a real regression. On 14 July it pinged: `bob/skill_invoked` had collapsed from five passes out of five to one out of five.

The four failures all said the same thing. Three flagged the skill `ahfu` and one flagged `linkedin` as "not a documented internal Workloft skill". Both are real, working skills we use daily. The judge is handed a short fleet-context block to stop it false-failing things it lacks knowledge of, and that block listed the valid skills by hand: `/go, /ship, /pizza, /running, /notes` and a few more. We had added `ahfu` and `linkedin` since, and nobody updated the list. So the judge, reasoning from its stale list, marked correct behaviour as a bug.

A soft hint was already in there ("an unfamiliar command is most likely another valid skill"), but the jurors overrode it and killed anyway, 3-0. We fixed it in two parts. First, the list now builds itself: `_known_skills()` enumerates the skills present on disk (`~/.claude/skills`) and unions them with a small curated set of the ones injected at session start, so a new skill landing can no longer age the list out. Second, we replaced the soft hint with a hard rule, phrased as absolutely as our temporal-grounding rule: a skill name being unfamiliar or absent from the list is never on its own a reason to fail the selection axis. The judge cannot see the full registry, so absence from its view proves nothing.

## Why it was worth doing

A judge that fails good work is worse than no judge. Every false kill spawns a fix-ticket for something that was never broken, and on our board that noise was already accumulating. We reproduced the exact failing case, scored it through the real code path, and watched it flip: `ahfu` went from a 3-0 kill to a 3-0 pass, accepted at the cheap screen stage with full confidence, never even reaching the panel. The important half is the control: we then fed the judge a genuinely wrong choice (invoking the pizza-coach skill when asked to ship code) and it still killed it, 2-0. The fix removed the false failures without blunting the axis that catches real ones.

## What's still off

Some skills are injected by the harness at session start and never touch the disk, so they cannot be auto-discovered; they live in the curated fallback and still need a human to add a brand-new one. The hard rule is the backstop for that gap, and on the no-human scoring path a single dissenting juror still vetoes, by design, so a truly unknown skill can still be questioned. That is the correct bias for an eval whose job is to catch bad output. What we fixed is narrower and more important: the judge no longer treats "I have not heard of it" as evidence of anything.
