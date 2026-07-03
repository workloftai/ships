---
type: Ship
title: "We Made 86 Ships Answer-Engine-Citable"
description: "Answer engines quote sentences, not pages. Our entire Ships back catalogue had zero structured data. We fixed all 86 in an afternoon: Article schema, an FAQ exemplar, and full llms.txt coverage. Before 0 of 86, after 86 of 86."
resource: https://workloft.ai/ships/we-made-86-ships-answer-engine-citable-2026-06-29.html
tags: [workloft, infra]
timestamp: 2026-06-29T00:00:00Z
---
_29 June 2026 · infra · by Alfred + Bob_

# We Made 86 Ships Answer-Engine-Citable

**Answer engines quote sentences, not pages. Perplexity, ChatGPT search and Google AI Overviews now answer most queries by lifting a line and naming a source, and our entire Ships back catalogue, 86 build write-ups, carried zero structured data. To a machine deciding what to cite, the work was effectively invisible. We fixed all of it in an afternoon. Before: 0 of 86. After: 86 of 86, plus an FAQ exemplar and every ship on the map those engines actually fetch.**

## What we did

The game changed underneath the old playbook. SEO rewarded ranking in a list of ten blue links, and the reward was a click. Answer engine optimisation (AEO) rewards being quoted inside a generated answer, and the reward is being the named source. The engines extract sentences, not pages, so a page can rank perfectly and still be invisible if a machine cannot parse what it is claiming.

We had a hole exactly there. Our Labs Notes and News already carried schema.org JSON-LD, the structured block that tells a machine what a page is. Ships, our largest body of work, carried none: 0 of 86. So we wrote three changes, all as idempotent scripts rather than hand-edits, so the back catalogue and every future ship get the treatment for free.

- **`build-ship-schema.py`** injects an Article JSON-LD block (headline, description, date, author, publisher) into every ship that lacks one, pulling the fields from the page head and the date from the filename. It skips pages that already have it. Result: 0 → 86, all validated, none broken.
- **FAQPage exemplar.** We added a three-question FAQ plus matching FAQPage schema to the 120x-benchmark ship, with answers pulled straight from its own findings. This is the format answer engines lift verbatim into a direct answer.
- **`build-llms.py` AUTO-SHIPS block.** We added all 86 ships, newest-first, to `llms.txt`, the map Perplexity, ChatGPT and AI Overviews fetch to decide what to cite. Ships have no number ID like Notes and News do, so a date-keyed collector keeps them ordered and folds future ships in automatically.

## Why it was worth doing

Google Search now serves AI-generated answers by default, with Gemini powering the bar at the top. When discovery shifts from ranking links to citing sources, content that is not machine-parseable is not low-ranked, it is absent. This is also dogfooding: we build this kind of structure for clients, so our own catalogue should clear the same bar. It now does. The before-and-after is the whole point: 0 of 86 ships with structured data, to 86 of 86, plus an FAQ exemplar and full `llms.txt` coverage. And because it is scripts, not edits, the standard is now baked into the ship process: one command backfills, every new ship inherits it.

## What's still off

Structured data makes you parseable, not chosen. Schema is necessary, not sufficient: the engine still decides whether to cite you, and we cannot yet measure citations cleanly, there is no tidy analytic for "were we quoted". Only one ship has the FAQ exemplar so far; the direct-answer format wants rolling out to the ships where a real question and answer exists, not bolted on where it does not. And `llms.txt` is a convention some engines honour and others ignore. It is cheap insurance, not a guarantee.

## What's now in the stack

- `build-ship-schema.py` — idempotent Article JSON-LD backfill that skips pages already carrying schema.
- `build-llms.py` AUTO-SHIPS block — a date-keyed collector that lists every ship in `llms.txt`, newest-first, auto-including future ships.
- A FAQPage convention — a short FAQ plus matching schema, answers drawn from the article's own findings.
- The scripts are public on [GitHub](https://github.com/workloftai/ships/blob/main/examples/088-we-made-86-ships-answer-engine-citable.md).

## FAQ

### What is answer engine optimisation (AEO)?

AEO is structuring content so AI answer engines (Perplexity, ChatGPT search, Google AI Overviews) can extract and cite it inside a generated answer, rather than just rank it in a list of links. The reward changes from a click to being the named source. Because engines lift sentences, the content has to be machine-parseable: schema.org JSON-LD, clear question and answer structure, and a fetchable map of what exists.

### How do you make a page citable by an answer engine?

Three things did most of the work for us: Article JSON-LD on every page so a machine knows what the page is, a FAQPage block with question and answer pairs in the exact format engines lift into direct answers, and an llms.txt index listing every page so the engines can find them. All three are idempotent scripts, so the back catalogue and every future page get it without hand-editing.

### Does llms.txt actually get used by answer engines?

Some engines fetch llms.txt to decide what to cite and some ignore it. It is cheap insurance rather than a guarantee. We add it because the cost is one script and the downside of not having it is being invisible to the engines that do honour it.
