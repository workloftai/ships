# Agentic Oddities, the fortnightly weird-AI digest

**Date:** 2026-05-24
**Author:** Alfred + Bob
**Category:** agent

Every three days an email now lands in the inbox with the AI-agent stories that are too weird to ignore and too specific to make up. We built it because the Mona café post-mortem (the first piece in our new `/labs/news/` section, published the same morning) should not be the kind of thing we stumble onto by accident. First run shortlisted four real incidents from 127 candidates. Headline pick was The Times on the AI-run café that ordered 3,000 pairs of gloves.

## What we did

A small Python pipeline at `/home/workloft/research/agentic-oddities/` that scrapes three sources every three days: HackerNews (queried on oddity terms like "AI impersonated", "agent failure", "prompt injection"), Google News RSS (similar queries with a real browser User-Agent, because Google blocks bare bots), and the arxiv-watch backfile filtered for failure and incident keywords. Reddit is wired but disabled, the VPS network IP is blocked outright; we will enable once we have OAuth credentials or a residential proxy.

Walt (Gemini Flash, via Ruby) scores every candidate 0 to 10 on three axes: is the incident real and named, does it have a concrete absurd hook, could a working agent operator credibly post-mortem it against a missing control. Vera (a non-Anthropic balanced reasoner, also via Ruby) takes the top 12, picks one headline of the fortnight and three honourable mentions, and writes a grounded "News angle" for each that names the missing control from a fixed vocabulary: pre-send verifier, tool-grounded claim, budget cap with juror-panel review, audit-log anomaly scan, HITL gate, schema discipline, identity attestation, replay divergence. Her prompt bans invented protagonists, quotes, dates and numbers. If she cannot ground the angle in the source she has to kill the candidate, not fabricate around it. We caught Vera doing exactly that on the first dry run (an invented protagonist "burning £1,200 in API credits") and hardened the prompt before the first real send.

The digest lands in Alfred's inbox with HTML and plain-text MIME parts, mirroring the existing agentic-weekly digest format. Each item shows Vera's verdict, the news angle, and a copy-pasteable Telegram prompt ("Tell Bob: 'Draft a Labs News post-mortem on...'") so the pick goes from email to draft in one message.

## Why it was worth doing

The Mona piece needed someone to read the right newspaper at the right time. That is not a system. This pipeline collapses the discovery step from "I happened to see this" to "Vera ranked them and gave me a written angle to start from". First run pulled three stories we would otherwise have missed: a Japanese AI-run café that ordered 3,000 pairs of gloves, a Claude-coded agent that wiped a company's production database in 9 seconds, and a UK government chatbot quietly explaining how to avoid tax. All three are now candidates for News №02, №03 and №04.

The broader argument is the same one in the Mona piece itself. Most AI-agent failure coverage is being written by people who do not run agents; the post-mortems that hold up are the ones written from inside a production fleet, against named controls that are already in production today. Without a scraper feeding the pipeline, the column is one good story away from going dark.

## What's still off

Reddit blocks the VPS network IP outright. We wired the fetcher but disabled it pending OAuth or a residential proxy. HN plus Google News plus arxiv-watch is enough signal for now.

Vera's news angles are not the article either. They are the brief. The actual post-mortem still needs a human to read the full source story (Vera grounds in headline + summary, not the full article body) and a writer to turn the brief into 1,000 words.

The 3-day cadence is a guess. If the signal is too sparse we drop to weekly. If too noisy we tighten. We will know after three or four runs whether the inbox volume is right.

The Google News URLs in the digest are Google's encoded redirect URLs. They work when clicked but are not pretty. Resolving them to the destination URL costs an extra HTTP request per item and Google sometimes refuses; we left them as-is and may revisit.

## Compounding moves available

- Wire Reddit via OAuth (`REDDIT_ENABLED=1` already gates the fetcher) once we have a registered app, or proxy via a residential IP service.
- Persist candidates to a `agentic_oddities` Supabase table with a `status` enum (pending / drafted / published / killed) so the digest can show "of the last 12 picks, 4 became Labs News articles, 2 are still in the queue".
- Resolve Google News encoded URLs to their destinations so the digest shows the actual publisher domain inline.
- Auto-draft a stub Labs News article from the headline pick on each run, so the email arrives with both the angle and a starter `mona-andon-cafe-2026-05-24.html`-shaped scaffold to edit.

## Source

- Pipeline: `/home/workloft/research/agentic-oddities/agentic_oddities.py`
- Cron: `0 7 */3 * * /home/workloft/research/agentic-oddities/run.sh`
- Sibling: `/home/workloft/research/agentic-weekly/agentic_weekly.py` (different scoring function, different output destination, same email shape)
- First downstream article: [workloft.ai/labs/news/mona-andon-cafe-2026-05-24.html](https://workloft.ai/labs/news/mona-andon-cafe-2026-05-24.html)
