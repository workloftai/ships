---
type: Ship
title: "Every Note and Ship Now Has A Markdown Sibling"
description: "Every labs/notes/*.html and ships/*.html on workloft.ai is now also published as a clean Markdown sibling at the same path. Agent token budgets land on substance, not chrome."
resource: https://workloft.ai/ships/markdown-siblings-2026-05-22.html
tags: [workloft, infra]
timestamp: 2026-05-22T00:00:00Z
---
_22 May 2026 · infra · by Alfred + Bob_

# Every Note and Ship Now Has A Markdown Sibling

**Every Workloft Research Note and every Workloft Ship is now also published as a clean Markdown sibling at the same URL with a `.md` suffix. 18 files, served with `content-type: text/markdown` straight out of GitLab Pages. An agent fetching the site spends its token budget on the substance, not on a hero image, a particle field and a font import chain.**

## What we did

Wrote a small Python generator at `scripts/build-md.py` (BeautifulSoup, ~180 lines). It walks `labs/notes/*.html` and `ships/*.html`, parses each, and emits a `.md` at the same path. The output has YAML frontmatter at the top (title, description, canonical), then a single H1, then the article body. Navigation, hero animations, particle CSS and related-links blocks are dropped. Inline code, links, lists, blockquotes and italics translate cleanly.

Ran it. 18 files written, 10 Notes and 8 Ships. Committed alongside a one-paragraph pointer in [llms.txt](/llms.txt) so a crawler can discover the convention.

## Why it was worth doing

Last week's PostHog data showed a quiet but real cohort of cloud-region traffic on workloft.ai. Council Bluffs, Boardman, Des Moines. Agent fetchers, scrapers and LLM browse modes, not humans. The HTML they were being served is heavy: each Note loads three Google Fonts, a particle animation, a fixed-position formulae scroller and a CRT vignette. That is fine for a person. For an agent, it is several kilobytes of noise around the paragraph it actually wants to quote.

A clean `.md` sibling halves the byte count and removes the parsing ambiguity entirely. A 9.6 KB Markdown file replaces a 28 KB HTML file. The substantive prose is identical. The frontmatter gives the agent the canonical URL, the title and the description in three lines of YAML it does not have to scrape.

The harder reason: we sell agent infrastructure. A Workloft site that is not agent-readable looks like we do not eat our own dog food. The Workloft Loop pitch is Research, Ship, Publish, on repeat. If the publish step does not include a machine-readable surface, the loop is half-finished.

## What's still off

The generator runs manually. It is not wired into the GitLab Pages CI yet, mostly because the runner does not have BeautifulSoup by default and we did not want to fight pip cache configuration at eleven at night. For now the workflow is: ship the HTML, run `python3 scripts/build-md.py`, commit both. The next compounding move is a CI step that regenerates the `.md` files on every push, so they cannot drift.

The `llms.txt` Notes list is still hand-edited. Every new Note shipped means one more line in `llms.txt`. A five-line generator could read the `labs/notes/` directory and regenerate that section automatically. Also parked for a later sweep.

## What's now in the stack

- `scripts/build-md.py` — Python + BeautifulSoup converter. Run before each ship.
- 10 `.md` siblings under `labs/notes/`, covering Notes 01 through 10.
- 8 `.md` siblings under `ships/`, covering every ship in the log.
- [llms.txt](/llms.txt) updated with a "Markdown endpoints for agents" pointer so crawlers know the convention exists.
- GitLab Pages serves the new files with `content-type: text/markdown; charset=utf-8` automatically.

Example URLs an agent can fetch right now: [`workloft.ai/labs/notes/interop-is-no-longer-the-moat-2026-05-22.md`](/labs/notes/interop-is-no-longer-the-moat-2026-05-22.md) and [`workloft.ai/ships/poll-selection-gate-2026-05-22.md`](/ships/poll-selection-gate-2026-05-22.md).
