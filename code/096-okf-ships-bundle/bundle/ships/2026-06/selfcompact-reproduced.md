---
type: Ship
title: "SelfCompact Reproduced"
description: "We reproduced the core mechanism of SelfCompact (arXiv:2606.23525): an agent that decides for itself when to compact its own context. On synthetic traces it lands 30 to 59% under fixed-interval summarisation with zero redo incidents."
resource: https://workloft.ai/ships/selfcompact-reproduced-2026-06-23.html
tags: [workloft, research]
timestamp: 2026-06-23T00:00:00Z
---
_23 June 2026 · research · by Alfred + Bob_

# SelfCompact Reproduced

**First, a few words in plain English. An *AI agent* is a program that works through a task in steps, like a very fast assistant. As it works it builds up a *context* (its short-term memory — every note, result and bit of working-out it is holding). That memory is what you pay for: AI is billed by *tokens* (chunks of text, roughly a few characters each), and the bigger the memory, the more it costs on every step. *Compacting* means tidying that memory down to just what still matters.**

A new research paper, SelfCompact, has a neat idea: let the agent decide for itself *when* to tidy its own memory, rather than doing it on a fixed timer. We rebuilt the core of that idea ourselves. On 40 made-up test runs it used 30 to 59% fewer tokens than tidying on a timer, and 89% fewer than never tidying at all — and it never once threw away work it still needed. This is a stripped-down model of the idea, not the paper's full test.

## What we did

The paper's idea has two parts that only work as a pair. One is a tool the agent can use to summarise its own memory. The other is a set of rules for *when* to use it. The rules are the clever bit. Tidy up when a small job is finished, or when the work is clearly heading to an answer. Hold off in the middle of working something out, or when stuck. The agent makes the call itself, with no special retraining. The paper reports that this matches or beats tidying on a timer, while using 30 to 70% fewer tokens per question.

We rebuilt the idea, not the full test. Our version is two small Python files using nothing but the basics. It captures the thing that actually makes memory expensive: the agent re-reads its *whole* memory on every single step, so a bigger memory costs you over and over. That is the runaway cost that tidying is meant to stop. When a small job is done, our tidy-up swaps its long working-out for the one clean result it produced — nothing later in the task loses anything it needed. The decision rule is a simple stand-in, built with the exact same shape a real AI would plug into, so a live model can be dropped in later without changing anything else. We kept the stand-in as the default so the whole thing runs in seconds with no paid AI calls.

## Why it was worth doing

It reproduces the paper's central trade-off, and the numbers come straight out of how the thing works, rather than being hand-tuned to look good. Across 40 test runs of 12 small jobs each:

- **vs never tidying up:** 89.3% fewer tokens (456k → 49k on average).
- **vs the best timer setting:** 29.7% fewer tokens.
- **vs the worst timer setting:** 58.7% fewer tokens.
- **work thrown away by mistake:** 0 with SelfCompact, 1,887 across the timer settings.

That 30 to 59% range lines up almost exactly with the paper's reported 30 to 70%. The reason SelfCompact wins on cost *and* safety at the same time is that a timer is always a bad bargain. A fast timer tidies often and is cheap, but it keeps cutting in halfway through the agent's working-out, which forces it to redo the lost work (24 redos per run on the fast setting). A slow timer avoids most of that, but lets the memory grow fat in between (74% saving instead of 89%). SelfCompact dodges the choice: it tidies the instant a small job is done — as cheap as the fast timer — but never touches work in progress, so it never has to redo anything. This matters to us directly: Bob and the Loop (our own agents) build up a lot of memory over long runs, and we pay for it.

## What's still rough

To be straight about the limits: this is a simplified model of the idea, run in a way that gives the same numbers every time. It is not the paper's real tests (maths problems, live searching), not a real AI model, and no retraining is involved. The cost model, the made-up test runs and the decision rule are all deliberate simplifications, chosen to isolate the one idea. So read the percentages as "this shows the idea behaves the way the paper says", not as an official score. The next step, if we want to use this for real, is to swap the stand-in rule for a real AI decision and measure it on one of our own long-running agents.

## What's now in the stack

- `selfcompact.py` — the test-run model, the cost model, the tidy-up step and the decision rule.
- `run_experiment.py` — runs the comparison across 40 test runs and prints the table.
- A pluggable decision function, so a real AI judge drops in without changing the rest.
- Repeatable: same starting point, same numbers, checked across repeat runs.
