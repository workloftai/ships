# Agentic Social Posting Dedup

**Date:** 2026-06-06
**Author:** Alfred + Bob
**Category:** fix

Our publishing agent kept queuing posts we had already shipped. Same topic, second channel, days later. The problem was never the agent's memory, it was that the daily safety check was looking in the wrong place. We rebuilt it to read the real state of the queue, and the duplicates stopped.

## What we did

We run an agent that drafts social posts and queues them to a publishing tool, plus a daily audit meant to catch anything already published before it goes out twice. The audit was the broken part.

The old check only looked at the publishing calendar. But when you re-push a queue, the tool creates a fresh scheduled draft for each topic and leaves the previous one behind as an unscheduled draft with no slot. Unscheduled drafts never appear in the calendar, so the audit could not see them. They kept resurfacing topics we had already posted.

The rewrite is status-driven. Instead of trusting a cached schedule, it asks the publishing API for the live status of every tracked draft, then runs four passes:

1. Drop tracking for anything already published or deleted.
2. Collapse duplicate drafts of the same topic down to one and delete the orphaned leftovers.
3. Pull anything whose topic is already live in our post ledger, on its own channel or any other.
4. Close out the to-do items that match a post we have already shipped.

## Why it was worth doing

On the first proper run the new audit cleared nine orphaned duplicate drafts, killed one cross-channel repeat (a post live on one channel that was sitting as a draft on another), and auto-closed a stale to-do that was still asking us to publish something already out. One clean pass did what three manual reminders could not.

The deeper win is cross-channel awareness. We publish one topic to one channel on purpose, so the backlog actually moves. The old check was per-channel and could not tell that a topic live on one network was about to repeat on another. The new one treats the ledger as the single source of truth across every channel.

## What's still off

This is a safety net, not the root fix. The real discipline is to check the ledger before drafting anything, and to delete the old draft when you re-push a queue rather than leaving an orphan behind. The reconcile step matches to-dos on token overlap, tuned conservatively so it never closes the wrong task. That means the odd genuine duplicate with a very different title can still slip through to a human review. We would rather miss one than wrongly close work.
