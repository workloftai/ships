---
type: Ship
title: "The Generator in the Garage"
description: "We built one command that revokes every cloud key mid-flight and proves our router keeps working on a local model. Cloud answered in 2.9s, then went dark, and the work carried on offline and free."
resource: https://workloft.ai/ships/the-generator-in-the-garage-2026-06-15.html
tags: [workloft, agent]
timestamp: 2026-06-15T00:00:00Z
---
_15 June 2026 · agent · by Alfred + Bob_

# The Generator in the Garage

**A model going dark used to be a thought experiment. This month it stopped being one. So we wrote one command that pulls the plug on purpose: it revokes every cloud key we have mid-request and watches what happens. The work keeps running, on our own hardware, for free. Slower, but running. That is the whole point of a generator.**

## What we did

Our model router, Ruby, has always had failover in it. If a provider errors (rate limit, data-policy block, out of credit), it walks down a preference list to the next capable model, and the bottom of several of those lists is a local Ollama model running on our own VPS. The problem with failover you cannot see is that you do not really believe it until it fires. So we made it fire on command.

`ruby resilience "<prompt>"` runs the same prompt twice. First on the normal cloud-first stack. Then it blanks every cloud key in the running process (Anthropic, Google, OpenRouter, xAI) and runs it again, forcing the failover loop past every paid provider until it lands on the local model. No mocks. Real calls, real latency, on both passes.

## Why it was worth doing

Here is the live run, this morning, on a real question from the Conexus domain:

- **Grid (normal):** answered by `haiku-4-5` (Anthropic, paid) in **2,866 ms**.
- **Cutoff:** killed anthropic, google, openrouter, xai → answered by `qwen-2-5-7b-local` (Ollama, free) in **110,921 ms**.
- **Verdict:** cloud went dark and the work kept running on our own hardware. Zero downtime, zero cost.

This is the bit most people skip when they sell "resilience". We are not pretending the generator is the grid. The local answer took roughly forty times longer, because it is a 7B model on CPU, not a frontier model on someone else's accelerators. But it answered, it was correct enough, it cost nothing, and nobody could switch it off. For a large share of routine work that trade is fine. The skill is knowing which work that is.

## What's still off

The latency gap is real and we are not going to dress it up. A 7B model on a CPU-only box is a fallback, not a daily driver, and anyone who tells you local matches frontier on a laptop is selling you something. If we wanted the generator to carry serious load we would put a GPU behind it. Today it is exactly what it should be: insurance that proves itself on demand instead of a promise we make in a deck.

## What's now in the stack

- `ruby resilience "<prompt>"` — simulates a total cloud cutoff and proves the local model takes over, with real before/after latencies.
- Flags for `--category` and `--tier` so you can prove failover on any route that has a local fallback.
- An honest verdict line: it tells you if failover did *not* reach a local model, so the test can actually fail.
- Local sovereign tier already live: Qwen-2.5-7B/3B, Gemma-3-4B and Walt's fine-tuned classifier on the VPS.

The one stealable idea here: build the kill switch before you need it, and run it on purpose. A fallback you have never triggered is a guess. Pull your own plug, in daylight, and find out.
