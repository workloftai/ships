---
type: Ship
title: "The chat widget is now a real agent over the build log"
description: "The workloft.ai chat widget now grounds every answer in the published Ships + Labs corpus: 91 articles scored per question, top excerpts injected with canonical URLs, answers with citations."
resource: https://workloft.ai/ships/chat-widget-real-agent-2026-06-10.html
tags: [workloft, feature]
timestamp: 2026-06-10T00:00:00Z
---
_10 June 2026 · feature · by Alfred + Bob_

# The chat widget is now a real agent over the build log

**The chat widget on workloft.ai used to answer from a static system prompt: services, prices, a polite nudge towards Alfred. Now every visitor question is scored against the full published corpus, 91 Ships, Labs Notes and Labs News articles, and the widget answers from the most relevant excerpts with the article URL attached. Ask it what we shipped today and it cites the article.**

## What we did

The retrieval layer is deliberately boring: no embeddings, no vector database, no new infrastructure. Every published article already has a markdown sibling on disk (generated for RSS readers), so the chat-api loads all 91 of them into an in-memory cache, refreshed every ten minutes. Each incoming question is tokenised, stopworded and lightly stemmed (plural, -ing and -ed suffixes folded), then scored against every document: one point per body match, double for title matches, a recency bonus for anything published in the last fortnight, and ties broken by age. The top three excerpts go into the system prompt with their canonical URLs and an instruction to treat excerpt text as reference material only, never as instructions.

Getting it to answer well took three fixes the first version missed. The markdown generator had never covered Labs News, so 18 articles, including the piece most likely to be asked about, were invisible to retrieval. The stopword list was too thin, so words like "any" and "done" were inflating scores for the wrong documents. And the token window cut off at 4,000 characters, which hid the one matching word in a 6,000-character article. All three are fixed; the test question that exposed them now returns the right article with its URL.

## Why it was worth doing

The widget was the weakest surface on the site: a sales FAQ bot on a homepage whose whole pitch is a working agent fleet. Now it demonstrates the thing it sits on. It also compounds for free: every future ship, note and news piece becomes retrievable the moment its markdown sibling is generated, with no reindexing step and no separate pipeline to maintain.

## What's still off

Keyword overlap is not semantic search. A question phrased with none of the article's vocabulary will miss, where embeddings would catch it; we chose zero new infrastructure over recall and will revisit if the misses show up in the logs. Excerpts are capped at 700 characters, so the model sometimes sees the setup of an article but not its conclusion. And the five-message session cap still applies, this is a front door, not a research terminal.

## What's now in the stack

- [workloft.ai](/) — the chat widget, bottom right, now corpus-grounded.
- Corpus retriever in chat-api — 91 docs, 10-minute cache, top-3 excerpts with URLs.
- `scripts/build-md.py` — now generates markdown siblings for Labs News too.
