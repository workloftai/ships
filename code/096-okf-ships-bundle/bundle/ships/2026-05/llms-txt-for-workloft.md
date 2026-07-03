---
type: Ship
title: "llms.txt for Workloft, shipping for real this time"
description: "Our llms.txt existed in the repo for weeks and 404'd in production for weeks. A PostHog look at last week's traffic surfaced the silent failure. Fixed the CI, refreshed the content, made Workloft visible to AI crawlers."
resource: https://workloft.ai/ships/llms-txt-for-workloft-2026-05-22.html
tags: [workloft, infra]
timestamp: 2026-05-22T00:00:00Z
---
_22 May 2026 · infra · by Alfred + Bob_

# llms.txt for Workloft, shipping for real this time

**Our `llms.txt` existed in the repo for weeks. It also 404'd in production for weeks. Tonight a look at last week's traffic surfaced the silent failure. The visitor jump we were quietly pleased about was almost entirely AI crawlers fetching from GCP and AWS regions, and the one file purpose-built to answer them was missing. We fixed the deploy, refreshed the content, and made Workloft visible to agents.**

## What we did

The bug was clean. The GitLab Pages job copied `*.html` and a few subdirectories into `public/`. It did not copy `*.txt` or `*.xml`. So `llms.txt`, `robots.txt` and `sitemap.xml` all sat in the repo and returned 404. A two-line CI change now copies them.

Then we refreshed the content. The previous `llms.txt` listed Research Notes 01 to 05. Notes 06 to 10 had shipped since, including the two notes humans actually read this week (memory as substrate, skill packages not prompts). Added with one-line claims so an LLM can quote them back accurately. Sitemap got the same five entries plus the Ships log.

Two new sections that were not there before: a pointer to Workloft Ships (so crawlers find the active log of what we build), and an Internal Agent Fleet section listing Bob, Larry, Walt, Maggie, Gary, Otto, Ruby and Kit. Workloft's `llms.txt` is the only one we have seen that exposes the firm's own running agent stack. That is the demonstration, not the brochure.

## Why it was worth doing

PostHog showed 28 visitors over seven days, headline up 250%. Geography told the real story: clusters in Council Bluffs (Google Cloud), Boardman (AWS us-west-2), Des Moines (Azure), Monte Vista. That is not a sudden surge of humans. That is agent fetchers, scrapers and LLM browse modes. Real engaged traffic was closer to 10 to 17 sessions, a different and much smaller number.

If those crawlers are reading the site to answer a human's question, the question is no longer "do we rank on Google" but "does the LLM tell its human the right thing about us". Today they were being served a 404 on the file purpose-built to answer exactly that. Now they get a curated index: three service lines, ten research notes, eight named agents, contact details, repos. Side benefit: `robots.txt` is finally live too, with explicit allow for GPTBot, ClaudeBot, PerplexityBot, Google-Extended and the rest.

## What's still off

No measurement layer yet. PostHog still bundles Perplexity browse-mode fetches and real human-typed visits into the same Direct channel. That build is parked in Gary. The `llms.txt` content is also hand-maintained for now, so the next Research Note we ship will not auto-update it. A small generator that regenerates the Notes section from `labs/notes/` is the obvious next move, not done tonight.

## What's now in the stack

- [/llms.txt](https://workloft.ai/llms.txt) — 10 Notes, agent fleet, Ships pointer, concepts, provenance.
- [/robots.txt](https://workloft.ai/robots.txt) — explicit allow for major AI crawlers.
- [/sitemap.xml](https://workloft.ai/sitemap.xml) — current, including Ships and Notes.
- Two-line CI guard so future root-level `*.txt` and `*.xml` files ship by default.
