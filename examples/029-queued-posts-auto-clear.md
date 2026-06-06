# Queued posts auto-clear from the to-do list

**Date:** 2026-06-06
**Author:** Alfred + Bob
**Category:** agent

My to-do list kept reminding me to publish posts that were already staged in the review queue. The work was done, the reminder was not. So once a post is queued, the to-do that asked for it now closes itself. The draft becomes the tracker, and the list goes quiet.

## What we did

Our split for social posts is simple: the agent queues a post as an unscheduled draft, I review it and publish it myself. The agent never hits publish. That split is deliberate, but it left a gap. The "publish this" to-do only closed once the post was actually live, so every post queued and waiting on me still showed as an open task. I kept getting nagged about things already staged.

We already run a daily audit over the publishing queue that reconciles drafts against our post ledger. We added a fifth pass to it. For every open publish to-do, it now checks whether a matching draft is already queued, a live draft or a scheduled one we still track, matched by channel and by the tokens in the slug. On a confident match it closes the to-do and stamps it with the draft id, leaving a clean pointer back to the thing now waiting for review. The match is the same conservative token-overlap test the ledger pass uses: it needs strong agreement on the slug before it touches anything.

## Why it was worth doing

The first live run closed two open publish to-dos that were already queued and waiting, both at full slug match, and left every un-queued one alone. Re-running it changed nothing, which is the property you want from an audit: act once on real evidence, then stay quiet. The reminders for already-staged posts stopped.

A to-do should track work that still needs a human, not work parked in a review queue. Moving the tracking onto the draft itself means the list only ever shows what is genuinely outstanding. Less noise, and I trust the list more for it.

## What's still off

The close is a one-way door. If I delete a queued draft without publishing it, the to-do stays closed and will not reappear on its own, so the draft is the system of record from that point. The match is also tuned to be cautious, so a post whose to-do title is worded very differently from its slug can still slip through to a manual look. We would rather leave one reminder standing than close the wrong task.
