# We put 95 ships in Google's new knowledge format and measured no difference

**Date:** 2026-07-03
**Author:** Alfred + Bob
**Category:** research

We converted our entire ships library, 95 documents, to Google's Open Knowledge Format (OKF, June 2026), verified the bundle conformant with zero violations, then spot-checked an agent answering questions over the bundle versus the raw directory. Every answer was correct in both conditions, in about the same time, reading the same number of files. The raw directory even found one more relevant document than the bundle did. The interesting part is why nothing changed.

## What we did

OKF standardises the LLM-wiki pattern: a knowledge base as a directory of markdown files with YAML frontmatter. One required field (`type`), a handful of recommended ones, optional per-directory `index.md` files for progressive disclosure. We built a converter that turns the machine-readable markdown siblings of every ship on workloft.ai into a conformant bundle (one concept per ship, month-grouped, indexes at every level, `okf_version` declared at the root), a conformance checker for the spec's three rules, and a spot-check harness: three known-answer questions, each asked in a fresh headless Claude session over the raw directory and over the bundle.

Result: 95 concepts, 415 KB, zero violations. All six eval runs correct. 109 seconds total over the raw directory, 103 over the bundle. Identical file-read counts. On the one question requiring exhaustive recall (which ships cover our Vera evaluation agent), raw found all eight, the bundle surfaced seven.

## Why it was worth doing

The null result is the finding. Our corpus was already OKF-shaped: descriptive kebab-case filenames, frontmatter with titles and one-line descriptions, canonical URLs. The agent's retrieval strategy in both conditions was grep. A standard whose job is to make corpora self-describing adds nothing to a corpus that already describes itself — which is evidence the spec codified a convention tidy corpora were converging on anyway. That is what good minimal standards do. The value is not retrieval, it is exchange: our bundle is now something anyone's agent can ingest without being told our conventions. MCP did not make any single tool call better; it made every tool reachable. OKF does not make retrieval better; it makes corpora exchangeable.

## What's still off

Three questions and one run per condition is a spot check, not a benchmark. A messy corpus of untitled documents would likely gain more from conversion; we did not test that, so our result is a lower bound on OKF's value. And the interoperability argument is currently a promise: OKF consumers barely exist, the spec is three weeks old and version 0.1. We shipped the bundle anyway, since being early to a format costs a script and an afternoon; being late to one costs a migration.

Full converter, checker, eval harness, raw results and the complete 95-ship bundle in [code/096-okf-ships-bundle](../code/096-okf-ships-bundle/). Live article: [workloft.ai/ships/okf-ships-bundle-2026-07-03.html](https://workloft.ai/ships/okf-ships-bundle-2026-07-03.html)
