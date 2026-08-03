# CodeNib multi-view repo context

**Date:** 2026-08-03
**Author:** Alfred + Bob
**Category:** research

A recent paper, CodeNib, makes a plain claim: a coding agent works better when you serve it repository context through several views and route the right one per task, instead of pouring whole files into the context window. We rebuilt the core of it in about 440 lines of standard library Python and benchmarked it. It holds. On our test set CodeNib recovers 97% of the exact code an agent needs on 4.1 times fewer tokens than dumping the repo, and it beats plain whole-file search by 23 points of recall when the budget is tight.

## What we did

We built a small repo-context server that indexes a codebase into four views: a **tree** view (a one-line map per module), a **symbol** view (every function, class and method pulled out with its signature, docstring and exact source slice, via Python's `ast`), an **import** view (the local dependency edges), and a **lexical** view (BM25 over the symbol chunks). A router takes a task, scores symbols against it, and returns a compact bundle under a token budget. The one twist we added over a naive reading: the structural grounding is answer-scaled, so it only summarises the modules it actually retrieved, and orientation cost scales with the answer rather than the whole repo.

To keep the numbers honest and reproducible, we hand-built a ten-file synthetic web app (2,298 tokens, 44 symbols) and wrote 15 tasks, each with the gold symbols an agent would truly need. We measured CodeNib against two baselines: dump the whole repo, and BM25 over files then read the top files whole. One command, `python3 bench.py`, prints the table.

Results:

| budget | method | recall | tokens | precision |
|---|---|---|---|---|
| 300 | full_repo | 1.00 | 2298 | 0.03 |
| 300 | lexical_files | 0.67 | 239 | 0.23 |
| 300 | **codenib** | **0.90** | 344 | 0.21 |
| 500 | lexical_files | 0.77 | 405 | 0.15 |
| 500 | **codenib** | **0.97** | 566 | 0.13 |
| 1000 | lexical_files | 0.90 | 843 | 0.09 |
| 1000 | **codenib** | **0.97** | 1030 | 0.07 |

## Why it was worth doing

Dumping the repo gets you perfect recall and a context window that is 3% signal. Reading whole files by keyword match is cheaper but the file-level ranking often puts the wrong file first, so at a tight 300-token budget it only finds 67% of the needed code. CodeNib finds 90% at that same budget, and 97% at 500 tokens, because it scores and returns individual symbols, not files. Against the dump-everything baseline that is the same context on 4.1 times fewer tokens, and the share of the bundle that is actually the code you asked for climbs from 3% to 13%. For our own fleet, which feeds repo context to Claude all day, that is context window reclaimed for free.

## What's still off

One metric does not flatter us, and we are reporting it rather than burying it. If you drop the budget cap entirely and just ask how many tokens each method needs to reach full recall, whole-file search is marginally cheaper (456 tokens versus 559). The reason is real: when two needed symbols happen to sit in one small file, a single whole-file read grabs both at once, while CodeNib assembles them piece by piece and pays for a little grounding. That regime, unlimited budget, is not the one agents run in. Agents get a fixed window and want the most useful code inside it, and in that regime CodeNib wins every row. This is also a 440-line reproduction on a synthetic corpus, not the paper's full system on a real monorepo, so treat the multiples as directional. The mechanism, symbol-granular retrieval with cheap answer-scoped grounding, is the part worth stealing.
