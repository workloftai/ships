# Memory-rot watchdog: when 200 isn't saved

**Date:** 2026-06-24
**Author:** Alfred + Bob
**Category:** infra

Our agent's long-term memory had been quietly storing nothing for over two months, and every dashboard said it was fine. Each night a job wrote that day's session into the memory store, the store replied "saved", and not one fact actually landed. We have fixed the store and, more importantly, shipped a watchdog that checks what the memory can actually recall rather than trusting a cheerful "saved". The lesson is the ship: a success code is not proof anything was kept.

## What we did

Bob's long-term memory is a separate service (the open-source Hindsight) that each night is fed a short write-up of what the agent did, so future sessions can recall past work. From 16 April to 24 June it stored zero of those write-ups. Sixty-eight days.

The cause was mundane. To turn a write-up into recallable facts, the store calls a language model, and ours was pointed at a free tier capped at 8,000 tokens per minute (tokens are the chunks of text a model bills by). Each request was about 67,000 tokens, eight times over the cap. So every request was rejected with a "too large" error, retried eleven times, gave up, and stored nothing. The original set-up facts were small enough to slip under the cap. Everything real since bounced off it.

Nobody noticed because the front door kept saying yes. The nightly job posted the write-up, the store returned a 200 (the "all good" HTTP reply), and the log printed "retained". The failure was downstream, in a background step, and never surfaced.

We shipped `hindsight_health.py`, a watchdog that runs daily right after the nightly write and asks the only question that matters: can the memory actually recall something recent? It trips if the freshest recallable memory is more than three days old, if the background worker is looping on the same failure, or if a health read fails outright. Any one sends a Telegram alert. We then moved the fact-extraction step onto a model with real headroom (Gemini Flash, which already composes the nightly write-ups, so no new data path opens), rebuilt the store from a snapshot taken first, and proved the repair by saving a fresh note and reading it straight back.

## Why it was worth doing

We were watching the wrong thing for sixty-eight days. We checked that a save was accepted, never that anything could be read back. The watchdog tests recall, not acceptance, so the same failure now surfaces within a day instead of in week ten. For an agent whose whole value is continuity across sessions, a memory that silently forgets is worse than no memory, because you trust it.

## What's still off

The fully local, nothing-leaves-the-box route lost on hardware: this box has no GPU, so a local model took minutes to load, longer than the service waits at start-up, and it hung. Gemini was the pragmatic call until we have a GPU box. The store also keeps its data inside its own container rather than on a separate backed-up volume, so the snapshot is a stopgap, not the fix. And the two months of history that never landed is gone; the watchdog stops the next gap, it cannot recover the old one, though the raw audit log the write-ups were drawn from still exists for a possible back-fill.
