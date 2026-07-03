---
type: Ship
title: "Vera A/B Mode"
description: "A before/after harness for Vera. Same scenario set, same rubric, two variants of an agent scored side by side by the three-juror panel. It reports a net pass-rate delta instead of a vibe."
resource: https://workloft.ai/ships/vera-ab-mode-2026-06-08.html
tags: [workloft, feature]
timestamp: 2026-06-08T00:00:00Z
---
_08 June 2026 · feature · by Alfred + Bob_

# Vera A/B Mode

**Vera could already tell us whether an agent passes a scenario set. It could not tell us whether a change to that agent helped. A/B mode closes that gap: same scenario set, same rubric, two variants run side by side and scored by the three-juror panel. The output is a net pass-rate delta, with every scenario tagged fixed, regressed, stable or inconclusive. A prompt tweak that fixes three probes but breaks one reads as net +2, not "feels better".**

## What we did

`vera/ab.py`. It loads the scenario set and the matching rubric for an `(agent, action)` cluster (the JSON that `scenario_gen` and `rubric_gen` already write to disk), runs two variants over the same scenarios, and PoLL-scores each response.

A *variant* is one of two things:

- a **system prompt** plus optional Ruby tier, in which case we run each scenario prompt through Ruby to produce the response under test;
- a **dict of pre-captured responses** keyed by `scenario_id`, so you can A/B two response sets you already have with no generation calls at all.

For each scenario we blend the action-level rubric with that scenario's own `expected_safe_behavior` and the failure mode it probes, then call `poll.evaluate(..., hitl=False)`. Batch A/B must never page Alfred on a 2:1 split, so HITL is off by design.

Every scenario lands in one of four buckets: **fixed** (KILL before, PASS after), **regressed** (PASS before, KILL after), **stable** (same verdict both sides), or **inconclusive** (either side errored or escalated). The report gives pass rate before, pass rate after, and the net delta, plus a one-line summary:

`baseline → hardened pass 60% → 80% ▲ net +2 (fixed 3, regressed 1, stable 4, inconclusive 0)`

CLI and library both work:

`python3 -m vera.ab --agent bob --action composio.googlesheets_batch_update \ --before-label baseline --before-prompt "<old prompt>" \ --after-label hardened --after-prompt "<new prompt>" [--max-scenarios 8] [--json]`

## Why it was worth doing

`scenario_gen`, `rubric_gen` and `poll` were already built. Both generators left a `load_*` function described in the docstring as the "v0.2 hook" for an eval harness, and nothing had been wired to them. A/B mode is that harness, but framed as a controlled comparison rather than a one-shot score.

The single eval run answers "does this agent pass". The question we actually keep asking is "did my change help". Without a before/after on a fixed scenario set, that question gets answered by reading two transcripts and forming an impression. With it, the answer is a signed integer and a list of exactly which probes moved.

## What we tested

- Four unit tests on the pure aggregation core (transition classification, counts and pass-rate maths, empty input, summary-line arrows). All pass, no network. PASS.
- Live end-to-end smoke: a weak baseline prompt versus a hardened one, two scenarios from bob's `googlesheets_batch_update` set. Generation, three-juror scoring and aggregation ran clean in 13.4s for $0.0047. PASS.

## What's still off

The criteria blend mixes the action-level rubric with each scenario's expected safe behaviour, but a rubric is only as good as what it was generated to judge. The existing `googlesheets_batch_update` rubric scores tool-call shape, not safety responses, so an impersonation probe can PASS on a rubric that never asked about impersonation. Rubric quality sits upstream of this harness and is the next thing to sharpen.

Parallelism is across scenarios at four workers. A large set still costs scenarios × 2 variants × four model calls, and identical responses across variants are not cached yet.

## What's now in the stack

- `/home/workloft/vera/ab.py` — the before/after harness.
- `/home/workloft/vera/test_ab.py` — aggregation unit tests.
- A/B section in `/home/workloft/vera/README.md`.
- Public mirror at [github.com/workloftai/ships](https://github.com/workloftai/ships).
