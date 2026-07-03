---
type: Ship
title: "Memory-rot watchdog: when 200 isn't saved"
description: "Our agent's long-term memory silently stored zero facts for two months while every health check stayed green. The cause was a free-tier token cap that still returned success. Here is the failure, the fix, and the watchdog that now checks what is actually recallable instead of trusting the HTTP status."
resource: https://workloft.ai/ships/memory-rot-watchdog-2026-06-24.html
tags: [workloft, infra]
timestamp: 2026-06-24T00:00:00Z
---
_24 June 2026 · infra · by Alfred + Bob_

# Memory-rot watchdog: when 200 isn't saved

****Our agent's long-term memory had been quietly storing nothing for over two months, and every dashboard said it was fine. Each night a job wrote that day's session into the memory store, the store replied "saved", and not one fact actually landed. We only found it because we went looking. We have fixed the store and, more importantly, shipped a watchdog that now checks what the memory can actually recall, rather than trusting a cheerful "saved". The lesson is the ship: a success code is not proof anything was kept.****

## What happened

Bob, our main agent, has a long-term memory: a separate service (we use an open one called Hindsight) that each night is fed a short write-up of what the agent did that day, so future sessions can recall past work. From 16 April to 24 June it stored zero of those write-ups. Sixty-eight days. When we asked it "what did we ship this week", it answered with facts from the day it was first set up and nothing since.

The cause was mundane, which is the interesting part. To turn a write-up into recallable facts, the store calls a language model. Ours was pointed at a free tier with a cap of 8,000 tokens per minute (tokens are the chunks of text a model bills by; 8,000 is roughly a few thousand words). Each request it sent was about 67,000 tokens, eight times over the cap. So every request was rejected with a "too large" error, retried eleven times, gave up, and stored nothing. The very first set-up facts were small enough to slip under the cap. Everything real since bounced off it.

## Why nobody noticed

Because the front door kept saying yes. The nightly job posted the write-up, the store accepted the request and returned a success code (HTTP 200, the "all good" reply every web request hopes for), and the job's log dutifully printed "retained". The failure was downstream, in a background step, and it never surfaced. Nothing we watched was watching the right thing. We were checking that the save was accepted, not that anything could be read back.

## What we built

A small watchdog, `hindsight_health.py`, that runs every day right after the nightly write and asks the only question that matters: can the memory actually recall something recent? It trips on three signals. One, the freshest thing it can recall is more than three days old (if writes are happening but nothing newer comes back, facts are being dropped). Two, the background worker has been looping on the same failure. Three, a quick health read fails outright. Any one of those sends a message straight to Telegram.

The design point is deliberate: it does not check that a save was accepted. It checks that a real memory written today can be read back today. That is the test that would have caught this in April, on day one, instead of in week ten.

## The fix itself

We moved the fact-extraction step off the capped free tier onto Gemini Flash, a fast hosted model we already use for the nightly write-ups. That matters for a quiet reason: the day's write-up already passes through Gemini when it is first composed, so using Gemini to pull the facts out of it adds no new place for the data to go. The memories themselves and the search index stay on our own box. We rebuilt the service from a snapshot taken first (the store keeps its data inside itself, so a careless rebuild would have wiped it), then proved the repair the honest way: we saved a fresh note and immediately asked for it back. It came back. First time the full loop has worked since April.

## What is still off

- **The sovereign route lost on hardware.** We first tried a local model so nothing left the machine at all. This box has no GPU (the chip that makes models fast), so loading one took minutes, longer than the service waits at start-up, and it hung. Gemini was the pragmatic call. A local model becomes the right answer the day we have a GPU box.
- **The store keeps its data inside the container.** It should sit on a separate, backed-up volume so a rebuild can never threaten it. The snapshot is a stopgap, not the fix.
- **Two months of history is gone.** The watchdog stops the next gap; it cannot recover the write-ups that never landed. We still hold the raw audit log they were drawn from, so a back-fill is possible later.

## What is now in the stack

- `walt/hindsight_health.py`: the watchdog: three recall-based tripwires and a Telegram alert.
- A daily cron at 05:15 UTC, right after the nightly write, so a silent gap can last at most a day.
- The memory store's fact step moved to a model with real headroom, rebuilt from a snapshot with both memory banks intact.
