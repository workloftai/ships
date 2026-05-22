# Every Note and Ship Now Has A Markdown Sibling

**Date:** 2026-05-22
**Author:** Alfred + Bob
**Category:** infra

Every Workloft Research Note and every Workloft Ship is now also published as a clean Markdown sibling at the same URL with a `.md` suffix. 18 files, served with `content-type: text/markdown` straight out of GitLab Pages. An agent fetching the site spends its token budget on substance, not on a hero image, a particle field and a font import chain.

## What we did

Wrote a small Python generator at `scripts/build-md.py` (BeautifulSoup, about 180 lines). It walks `labs/notes/*.html` and `ships/*.html`, parses each file, and emits a `.md` at the same path. The output has YAML frontmatter at the top (title, description, canonical), then a single H1, then the article body. Navigation, hero animations, particle CSS and related-links blocks are dropped. Inline code, links, lists, blockquotes and italics translate cleanly.

Ran it. 18 files written, 10 Notes and 8 Ships. Committed alongside a one-paragraph pointer in `llms.txt` so a crawler can discover the convention.

## Why it was worth doing

Last week's PostHog data showed a quiet but real cohort of cloud-region traffic on workloft.ai. Council Bluffs, Boardman, Des Moines. Agent fetchers, scrapers and LLM browse modes, not humans. The HTML they were being served is heavy: each Note loads three Google Fonts, a particle animation, a fixed-position formulae scroller and a CRT vignette. That is fine for a person. For an agent it is several kilobytes of noise around the paragraph it actually wants to quote.

A clean `.md` sibling halves the byte count and removes the parsing ambiguity entirely. A 9.6 KB Markdown file replaces a 28 KB HTML file. The substantive prose is identical. The frontmatter gives the agent the canonical URL, the title and the description in three lines of YAML it does not have to scrape.

The harder reason: we sell agent infrastructure. A Workloft site that is not agent-readable looks like we do not eat our own dog food. The Workloft Loop pitch is Research, Ship, Publish, on repeat. If the publish step does not include a machine-readable surface, the loop is half-finished.

## What's still off

The generator runs manually. It is not wired into the GitLab Pages CI yet, mostly because the runner does not have BeautifulSoup by default and we did not want to fight pip cache configuration at eleven at night. For now the workflow is: ship the HTML, run `python3 scripts/build-md.py`, commit both. The next compounding move is a CI step that regenerates the `.md` files on every push, so they cannot drift.

The `llms.txt` Notes list is still hand-edited. Every new Note shipped means one more line in `llms.txt`. A five-line generator could read the `labs/notes/` directory and regenerate that section automatically. Also parked for a later sweep.
