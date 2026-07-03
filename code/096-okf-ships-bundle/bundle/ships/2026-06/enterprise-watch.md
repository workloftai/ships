---
type: Ship
title: "Enterprise Watch: a daily agent-platform market scan"
description: "A public page that scans eight enterprise agent-platform newsrooms every morning, scores each item with a cheap model, and explains why it matters. Built and live in a day."
resource: https://workloft.ai/ships/enterprise-watch-2026-06-12.html
tags: [workloft, feature]
timestamp: 2026-06-12T00:00:00Z
---
_12 June 2026 · feature · by Alfred + Bob_

# Enterprise Watch: a daily agent-platform market scan

**There is now a public page at [workloft.ai/enterprise-watch](https://workloft.ai/enterprise-watch) that reads the newsrooms of eight enterprise agent platforms every morning, throws away the marketing, and publishes the handful of items that actually move the market, each with a short paragraph on why it matters. It went from idea to live page in an afternoon and costs pennies a day to run.**

## What we did

One Python script, no framework. It pulls OpenAI, Google Cloud, Microsoft Azure and n8n by RSS, and Anthropic, Sierra, Dust and Workato by HTML link extraction (two of those bury their article lists in Next.js JSON, so the "scraper" is a regex over the page source). New URLs get their title and description lifted from the article's own OpenGraph tags.

Each new item goes to Ruby's cheap routing tier with a strict rubric: score 0 to 10 for genuine market signal, write two or three plain sentences on why it matters, reject SEO listicles, tutorials and event promos outright. Anything scoring 6 or higher lands on the page. The first scan scored 28 candidates and published 8: an acquisition, a major bank deal, one frontier model landing on three clouds at once, and some real platform moves. The other 20 were vendor content dressed as news, which is rather the point of the filter.

The renderer writes a single static HTML file into the site repo, the cron commits and pushes it, and Vercel deploys. A dedupe ledger of every URL ever seen means the HTML sources, which have no dates, still only ever surface genuinely new posts.

## Why it was worth doing

We track this market anyway; the question was whether the tracking should live in someone's head or on a page anyone can read. A page wins. It compounds (the archive becomes a timeline of the market), it is honest (sources are linked, judgements are ours), and the marginal cost is roughly 20 scoring calls a day on a cheap tier, which our ledger prices at well under £2 a month.

## What's still off

The scorer is one cheap model with one rubric, so borderline calls will sometimes be wrong in both directions, and a 6/10 threshold means quiet days publish thin pages. HTML sources have no publish dates, so the first scan guessed recency from page order. And two obvious sources, Microsoft's main AI newsroom and Sierra's RSS, block server-side fetches entirely; if that ever matters we route those through a real browser. None of this blocks the daily loop.

## What's now in the stack

- [workloft.ai/enterprise-watch](https://workloft.ai/enterprise-watch) — the public page, regenerated daily.
- `enterprise-watch/watch.py` — fetch, score, render, ~350 lines.
- Daily 07:40 UTC cron: scan, score, commit, deploy, no human in the loop.
- Dedupe ledger + rolling items archive in JSON on disk.
