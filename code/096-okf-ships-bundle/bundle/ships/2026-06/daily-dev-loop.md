---
type: Ship
title: "daily.dev wired into the Workloft Loop"
description: "We connected daily.dev's trending feed to the Workloft Loop. A daily cron pulls the feed, Walt scores each post against our research axes, and the strongest buildable picks file themselves into the backlog."
resource: https://workloft.ai/ships/daily-dev-loop-2026-06-06.html
tags: [workloft, ship]
timestamp: 2026-06-06T00:00:00Z
---
_6 June 2026 · infra · by Alfred + Bob_

# daily.dev wired into the Workloft Loop

**Our research backlog should be fed by what's actually moving in the field, not by whatever we happened to read. So we hooked daily.dev's trending feed into the Loop. A cron pulls it every morning, Walt scores each post against our research axes, and the strongest buildable ones file themselves into the backlog before we've had coffee. First run scored sixty posts and filed two. It is the third external signal feeding the Loop, and it cost a few pennies a day to run.**

## What we did

daily.dev ships a Public API on their Plus tier, so we subscribed and took the key. The documented `/feeds` endpoint is wrong (it 404s); the real ones live behind `/feeds/popular`, `/feeds/foryou` and `/search/posts`, which we found by reading the OpenAPI spec rather than the prose docs. The puller hits the popular and for-you feeds, dedupes by post id, and hands the batch to Walt.

Walt is Gemini Flash via Ruby on the cheap tier. It scores every post 0 to 10 against the same seven research axes we use for arXiv and Hugging Face papers: agent infrastructure, evaluation, retrieval and memory, tool use, cost and latency, security, and sovereignty. Anything at eight or above that is buildable on our stack in one to three days gets filed into Gary as a `#loop` research item, capped at two a day so it cannot flood the backlog. Everything scored goes into a daily digest.

## Why it was worth doing

The Loop already runs on external signal: arXiv-Watch for the paper firehose, Hugging Face Daily for community-curated ML, and now daily.dev for the dev-news layer, the releases and write-ups that never make it to arXiv. Three feeds, one scoring function, one backlog. Because the daily.dev scorer is a near-copy of the Hugging Face one, a post and a paper get judged by the same rubric, so the items competing for our attention are genuinely comparable.

First run, sixty posts in: it filed a cold-start evaluation of five AI models reviewing a deliberately buggy repo, and a piece on "intent debt" in agentic systems. Both landed in the Loop without a human touching anything. The whole thing runs on Gemini Flash, so a day's scoring costs a few pennies.

## What's still off

daily.dev is noisier than arXiv. It carries hype, tutorials of basics and opinion pieces alongside the real signal, so the scorer's job is mostly saying no, and the threshold will need tuning as we watch what it files over a week. The digest is also internal for now: it writes to disk and feeds Gary, but it does not yet surface anywhere we read by default. The obvious next move is to fold the top of the digest into the Monday Agentic Weekly so the trend layer gets a human read, not just an auto-file.

## What's now in the stack

- daily.dev Plus is a live feed source, pulled daily at 08:10 UTC.
- A Walt scorer that shares its rubric with the arXiv and Hugging Face pipelines, so papers and posts compete on equal terms.
- A daily trends digest written to disk, plus auto-filed `#loop` candidates in Gary, capped at two a day.
- One more external signal feeding the Loop, on top of arXiv-Watch and Hugging Face Daily.
