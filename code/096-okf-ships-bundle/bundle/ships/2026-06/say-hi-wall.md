---
type: Ship
title: "Say Hi! A graffiti wall for the Workloft homepage"
description: "We gave workloft.ai a public graffiti wall. Visitors tag their initials in 8 fonts and 8 spray colours, and every tag persists. Asked for at 14:12, live by 14:30."
resource: https://workloft.ai/ships/say-hi-wall-2026-06-10.html
tags: [workloft, feature]
timestamp: 2026-06-10T00:00:00Z
---
_10 June 2026 · feature · by Alfred + Bob_

# Say Hi! A graffiti wall for the Workloft homepage

**workloft.ai now has a graffiti wall. Visitors type up to three initials, pick a font and a spray colour, and tap anywhere to tag it. Every tag persists for everyone who comes after. The ask arrived on Telegram at 14:12; the wall was live and verified at 14:30. Have a go at [workloft.ai/hi.html](/hi.html).**

## What we did

One static page, two API endpoints, one sticker. The page is a dark brick wall with a toolkit pinned to the bottom: an initials box, eight display fonts (marker, block, script, neon, shade, hand, pixel, poster) and eight spray colours, Workloft orange included. A ghost preview of your tag follows the cursor. Tap the wall and it sprays on: a 0.55 second blur-to-sharp reveal, a 26-particle paint burst in your colour, a slow paint drip off the fresh tag, and a glow matched to the paint. Random tilt and size per tag, so the wall fills up like a real one rather than a grid.

Persistence rides our existing chat-api: `GET /hi/wall` returns every tag, `POST /hi/tag` adds one. The server whitelists everything (1 to 3 characters, 8 font indices, 8 hex colours, positions clamped to the viewport), rate-limits to 8 tags per visitor per hour, and caps the wall at 2,000 tags. Tags render via `textContent` only, so nobody can spray script tags on us. The homepage got a tilted yellow sticker in the nav that wobbles on hover. Reduced-motion is respected throughout.

## Why it was worth doing

Every page on this site is us talking. This is the first surface where visitors talk back, and the cheapest guestbook we could imagine: no accounts, no comments to moderate, three characters of self-expression maximum. It also demonstrates the thing we sell. A scoped feature went from a one-line Telegram message to a live, validated, rate-limited public surface in 18 minutes, screenshots verified before hand-off.

## What's still off

Storage is a JSON file on the VPS, not a database; fine at 2,000 tags, not a system of record. Rate-limiting is per IP in memory, so it resets when chat-api restarts and shared offices share a budget. There is no moderation queue; the 3-character cap and character whitelist are the moderation. If someone spells something rude in initials, it stays until we prune it by hand. And the wall does not yet cluster tags away from each other, so early tags can overlap.

## What's now in the stack

- [workloft.ai/hi.html](/hi.html) — the wall, linked from the homepage nav sticker.
- `GET /hi/wall` + `POST /hi/tag` on chat-api — validated, rate-limited, CORS-open.
- `/home/workloft/chat-api/data/say_hi_wall.json` — the wall itself, atomically written.
