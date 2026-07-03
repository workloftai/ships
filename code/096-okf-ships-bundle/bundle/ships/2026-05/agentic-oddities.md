---
type: Ship
title: "Agentic Oddities, the fortnightly weird-AI digest"
description: "A 3-day-cadence scraper that pulls real-world AI-agent failure stories from HN and Google News, scores them with Walt, has Vera pick the headline and the missing-control angle, and emails the digest to Alfred. First run shortlisted 4 from 127. Feeds /labs/news/."
resource: https://workloft.ai/ships/agentic-oddities-2026-05-24.html
tags: [workloft, agent]
timestamp: 2026-05-24T00:00:00Z
---
_24 May 2026 · agent · by Alfred + Bob_

# Agentic Oddities, the fortnightly weird-AI digest

**Every three days an email now lands in our inbox with the AI-agent stories that are too weird to ignore and too specific to make up. We built it because the Mona café post-mortem (the first piece in our new [Labs News](/labs/news/) section, published this morning) should not be the kind of thing we stumble onto by accident. First run shortlisted four real incidents from 127 candidates.**

## What we did

A small Python pipeline at `/home/workloft/research/agentic-oddities/` that scrapes three sources every three days: HackerNews (queried on oddity terms like "AI impersonated", "agent failure", "prompt injection"), Google News RSS (similar queries, real browser User-Agent because Google blocks bots), and the arxiv-watch backfile filtered for failure and incident keywords.

Walt (Gemini Flash, via Ruby) scores every candidate 0 to 10 on three axes: is the incident real and named, does it have a concrete absurd hook, could a working agent operator credibly post-mortem it. Vera (a non-Anthropic balanced reasoner, also via Ruby) takes the top 12, picks one headline of the fortnight and three honourable mentions, and writes a grounded "News angle" for each that names the missing control from a fixed vocabulary (pre-send verifier, tool-grounded claim, budget cap with juror-panel review, audit-log anomaly scan, HITL gate, schema discipline, identity attestation, replay divergence). Her prompt bans invented protagonists, quotes and numbers. If she cannot ground the angle in the source, she has to kill the candidate, not fabricate around it.

The digest lands in Alfred's inbox with HTML and plain-text MIME parts, mirroring the agentic-weekly digest format. Each item shows Vera's verdict, the news angle, and a copy-pasteable Telegram prompt ("Tell Bob: 'Draft a Labs News post-mortem on...'") so the pick goes from email to draft in one message.

## Why it was worth doing

The Mona piece needed someone to read the right newspaper at the right time. That is not a system. This pipeline collapses the discovery step from "I happened to see this" to "Vera ranked them and gave me a written angle to start from". First run pulled three stories we would otherwise have missed: a Japanese AI-run café that ordered 3,000 pairs of gloves, a Claude-coded agent that wiped a company's production database in 9 seconds, and a UK government chatbot quietly explaining how to avoid tax. All three are now candidates for News №02, №03 and №04.

## What's still off

Reddit blocks the VPS network IP outright. We wired the fetcher but disabled it pending OAuth or a residential proxy. HN plus Google News plus arxiv-watch is enough signal for now. Vera's news angles are not the article either, they are the brief. The actual post-mortem still needs a human to read the full source story and write the 1,000 words. And the 3-day cadence is a guess. If the signal is too sparse we drop to weekly. If too noisy we tighten.

## What's now in the stack

- `/home/workloft/research/agentic-oddities/agentic_oddities.py` — the pipeline.
- `./run.sh` — cron entrypoint, sources `/home/workloft/.hermes/.env` for Zoho + Ruby credentials.
- Cron: `0 7 */3 * * /home/workloft/research/agentic-oddities/run.sh` (07:00 UTC = 08:00 BST, every three days).
- Seen-store at `data/seen.json` (capped at 500 entries) so the same story does not feature twice.
- Per-run artefacts: `oddities-YYYY-MM-DD.json`, `.shortlist.json`, `.vera.json`.
- Sibling to `/home/workloft/research/agentic-weekly/` but with a different scoring function (incident over invention) and a different output destination (Labs News over reading list).
