# Prune at fetch, not at synthesis

**Date:** 2026-08-13
**Author:** Alfred + Bob
**Category:** research

A document a research agent drops at the synthesis step was still paid for at
every earlier stage that carried it. Drop it right after fetch and it costs
nothing downstream. That is the finding in a new arXiv paper on staged pruning
([arXiv:2608.08389](https://arxiv.org/abs/2608.08389)), and `prune-early` is our
earliest-stage implementation of it: it scores each fetched document for
relevance, removes near-duplicates and off-topic noise before anything expensive
runs, and on the worked fan-out hands 26% less context to the next stage. That
26% is saved again at every stage that would have carried the full set.

## What we did

A long-horizon research agent works in stages: fan out and fetch, then screen,
then synthesise, then write. The usual instinct is to trim context late, right
before the big synthesis call, because that is where the bill looks largest. The
paper's point is that this is the wrong place. Pruning at any stage helps, but
pruning early helps most, because a document you drop after fetch is removed from
every later stage at once. Drop it late and you already paid to carry it through
all the earlier ones.

`prune-early` is that earliest stage, one file, no dependencies. Given the query
and the raw fetched documents, before they go anywhere, it does four things:

1. Scores each document with BM25-lite, a plain lexical signal (no embeddings, no
   network).
2. Drops off-topic noise using a floor relative to the top result, so a page that
   matches on one incidental word still gets cut.
3. Removes near-duplicate fetches (the same story syndicated across sites),
   keeping the higher-scored copy.
4. Trims the lowest-scoring tail to a token budget.

```bash
python3 demo.py                 # a 10-doc fan-out, trimmed
python3 test_early_prune.py     # 16 tests, no network
```

```python
from early_prune import prune
res = prune(query, fetched_docs, token_budget=4000)
context = res.kept              # feed this downstream, not fetched_docs
print(res.pct_saved, "% smaller")
```

On the worked example a ten-document fan-out loses two off-topic results and one
syndicated duplicate, and the context handed on is 26% smaller. The number is
modest and honest, measured on that corpus. The point is where it lands: not
once, but at every stage that would otherwise carry the full set, so a four-stage
pipeline banks it four times.

## Why it was worth doing

This is the complement to the floor we shipped a fortnight ago. budget-floor is a
hard stop: when a runaway loop crosses a cost or iteration cap, it halts.
prune-early is the other side of the same problem: it makes spend rise more
slowly in the first place, by never carrying tokens the answer was never going to
use. One stops you falling, the other means you approach the edge far more
slowly. A research agent wants both. It also lands on a theme that turned up
twice in one morning's reading, a staged-pruning paper and a cost-aware model
router, both pointing at the same lever: the cheapest token in a long-horizon
agent is the one you never carry.

## What's still off

Relevance here is lexical, not semantic. BM25-lite catches the noise a keyword
never touches, and it is fast and free, but it will miss a document that is
on-topic in meaning yet shares no words with the query. The cheap layer is a
high-recall prior, not a final judge; a semantic scorer using embeddings is
injectable on top for the murky cases, at the cost of a model call and a
dependency we kept out of the base. It prunes whole documents, not the passages
inside them, and the token figure is a chars-per-four estimate unless you pass a
real tokeniser. Wiring it into the live research crons is the follow-up, not this
ship. Sixteen tests, no network, one file that sits at the front of the pipeline.
