# prune-early: drop the tail before it compounds

A long-horizon research agent fetches documents, then screens them, then
synthesises, then writes. Every junk document it drops at the *synthesis* stage
was still paid for at every earlier stage that carried it. The same document
dropped right after *fetch* is paid for nowhere downstream.

That is the finding in "pruning strategies applied at different pipeline stages"
(arXiv 2608.08389): pruning at any stage helps, but early pruning helps most,
because an early cut removes a token from every later stage at once. The saving
multiplies with pipeline depth.

`early_prune.py` is that earliest stage. Zero dependencies, stdlib only.

## What it does

Given the query and the raw fetched documents, before they are carried anywhere:

1. **Scores** each document for query relevance with BM25-lite (no embeddings, no
   network).
2. **Drops off-topic noise** the search dragged in, using a relative floor so a
   document that overlaps the query on one incidental word still gets cut.
3. **Removes near-duplicate fetches** (the same story syndicated on three sites),
   keeping the higher-scoring copy.
4. **Enforces a token budget or keep-ratio**, dropping the lowest-scoring tail.

What comes out is the smaller head worth carrying. On the worked example in
`demo.py`, a 10-document fan-out loses two off-topic results and one syndicated
duplicate, and the context handed to the next stage is 26% smaller. That 26% is
saved again at every stage that would otherwise have carried the full set.

## Use

```python
from early_prune import prune

# right after your fetch / search fan-out, before the expensive synthesis call
res = prune(query, fetched_docs, token_budget=4000)

context = res.kept                 # feed this downstream, not fetched_docs
print(res.pct_saved, "% smaller")  # what you no longer pay for, per stage
for d in res.dropped:
    print(d.index, d.reason, d.detail)   # off-topic | duplicate | over-budget
```

`docs` can be plain strings or dicts (set `text_key`). Order is preserved. Token
counts default to a chars/4 estimate; pass `token_counter=` for exact figures.

## Where it plugs into our fleet

Any agent that fans out then feeds the results into a model call. Otto's daily
research hands fetched entries to Ruby for ranking; the deep-research harness
fans out searches then synthesises. Both carry every fetched result into the
expensive step today. `prune(query, results, token_budget=...)` between the fetch
and the model call is the drop-in. Wiring it into the live crons, and calibrating
the budget per agent, is the follow-up, not this ship.

## What's still off

- **Relevance is lexical, not semantic.** BM25-lite catches the noise a keyword
  never touches; it will not catch a document that is on-topic in meaning but
  shares no words with the query. For that you need an embedding scorer, which
  brings a model call and a dependency. The cheap layer is the high-recall prior;
  a semantic pass is injectable on top for the murky cases.
- **The token count is an estimate** unless you pass a real tokeniser. The
  chars/4 default is directionally right for English prose and good enough to set
  a budget, not to bill against.
- **It prunes documents, not sentences within them.** Cutting a long kept
  document down to its relevant passages is a finer-grained pass we have not
  built here.

Sixteen tests, no network, one file. Run `python3 test_early_prune.py` and
`python3 demo.py`.
