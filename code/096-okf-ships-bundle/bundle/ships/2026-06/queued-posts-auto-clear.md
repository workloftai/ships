---
type: Ship
title: "Queued posts auto-clear from the to-do list"
description: "Once a post is queued for review, the reminder to publish it now closes on its own. A new audit pass matches open publish to-dos to live drafts and takes them off the list."
resource: https://workloft.ai/ships/queued-posts-auto-clear-2026-06-06.html
tags: [workloft, ship]
timestamp: 2026-06-06T00:00:00Z
---
_6 June 2026 · agent · by Alfred + Bob_

# Queued posts auto-clear from the to-do list

**My to-do list kept reminding me to publish posts that were already sitting in the review queue, staged and waiting. The work was done, the reminder was not. So I changed the rule: once a post is queued for review, the to-do that asked for it now closes itself. The draft becomes the tracker, and the list goes quiet.**

## What we did

Our division of labour for social posts is simple. The agent queues a post as an unscheduled draft, I review it and publish it myself. The agent never hits publish. That split is deliberate, but it left a gap: the "publish this" to-do only closed once the post was actually live, so every post that was queued and waiting on me still showed up as an open task. I kept getting nagged about things that were already staged.

We already run a daily audit over the publishing queue that reconciles drafts against our post ledger. We added a fifth pass to it. For every open publish to-do, it now checks whether a matching draft is already queued, a live draft or a scheduled one that we still track, matched by channel and by the tokens in the slug. On a confident match it closes the to-do and stamps it with the draft id, so there is a clean pointer back to the thing that is now waiting for review.

The match is the same conservative token-overlap test the ledger pass uses: it needs strong agreement on the slug before it touches anything. A queued post is enough evidence to close the reminder, because the reminder has done its whole job once the draft exists.

## Why it was worth doing

The first live run closed two open publish to-dos that were already queued and waiting, both at full slug match, and left every un-queued one alone. Re-running it changed nothing, which is the property you want from an audit: it acts once on real evidence, then stays quiet. The reminders I was getting for already-staged posts simply stopped.

The point is that a to-do should track work that still needs a human, not work that is already parked in a review queue. Moving the tracking onto the draft itself means the list only ever shows me what is genuinely outstanding. Less noise, and I trust the list more because of it.

## What's still off

The close is a one-way door. If I delete a queued draft without publishing it, the to-do stays closed and will not reappear on its own, so the draft really is the system of record from that point. The match is also tuned to be cautious, which means a post whose to-do title is worded very differently from its slug can still slip through to a manual look. We would rather leave one reminder standing than close the wrong task.
