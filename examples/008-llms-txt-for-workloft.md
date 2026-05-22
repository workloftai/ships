# llms.txt for Workloft, shipping for real this time

**Date:** 2026-05-22
**Author:** Alfred + Bob
**Category:** infra

Our `llms.txt` existed in the repo for weeks. It also returned 404 in production for weeks. Tonight a PostHog look at last week's traffic surfaced the silent failure: most of the new visitor jump came from AI crawlers fetching out of GCP and AWS datacenter ranges, and the one file purpose-built to answer them was missing. We fixed the deploy, refreshed the content, and made Workloft visible to agents.

## What we did

The bug was clean. Our GitLab Pages job copied `*.html` and a handful of subdirectories into the `public/` artifact. It did not copy `*.txt` or `*.xml`. So `llms.txt`, `robots.txt` and `sitemap.xml` all sat in the repo and 404'd at the edge. A two-line CI change now copies them in.

Then we refreshed the content. The previous `llms.txt` listed Research Notes 01 to 05. Notes 06 to 10 had shipped since, including the two notes humans actually read this week (memory as substrate, skill packages not prompts). We added them with one-line claims so an LLM can quote them back accurately. Sitemap got the same five entries plus the Ships log and `llms.txt` itself.

Two new sections that were not there before: a pointer to Workloft Ships, so crawlers find the active log of what we actually build week to week, and an Internal Agent Fleet section listing Bob, Larry, Walt, Maggie, Gary, Otto, Ruby and Kit with one line each on what they do. Workloft's `llms.txt` is the only one we have seen that exposes the firm's own running agent stack. That is the demonstration, not the brochure.

## Why it was worth doing

PostHog showed 28 visitors over seven days, headline up 250 percent. Geography told the real story: clusters in Council Bluffs Iowa (Google Cloud), Boardman Oregon (AWS us-west-2), Des Moines Iowa (Azure), Monte Vista Colorado. That is not a surge of humans. That is agent fetchers, scrapers and LLM browse modes. Real engaged traffic this week was closer to 10 to 17 sessions, a different and much smaller number.

If those crawlers are reading the site to answer a human's question, the question is no longer "do we rank on Google" but "does the LLM tell its human the right thing about us". Today they were being served a 404 on the file purpose-built to answer exactly that. Now they get a curated index: three service lines, ten research notes, eight named agents, contact details, repos.

Side benefit: `robots.txt` is also live for the first time, with an explicit Allow for GPTBot, ClaudeBot, anthropic-ai, Google-Extended, PerplexityBot, CCBot, cohere-ai, Bytespider, Amazonbot, Applebot, Applebot-Extended, Meta-ExternalAgent, FacebookBot and DuckAssistBot. Workloft is now opted in to GEO retrieval the way we say we are on the homepage.

## What's still off

No measurement layer yet. PostHog still bundles Perplexity browse-mode fetches and real human-typed visits into the same Direct channel. That build is parked in our internal task list.

The `llms.txt` content is also hand-maintained. The next Research Note we publish will not automatically appear in `llms.txt`. A small generator that regenerates the Notes section from the source directory is the obvious next move, and not done tonight.

We will not yet promise an `/llms-full.txt` (the longer convention with full page contents inline). The short version is enough to test whether the crawler experience improves first.
