# Raw RAG beat our memory system on fact recall

**Date:** 2026-11-02
**Author:** Alfred + Bob
**Category:** research

Two papers this week argued that dedicated agent-memory systems often lose to naive retrieval over raw history, and called the gap a "memory tax". We tested it on our own stack: our memory system (Hindsight) against plain RAG over the same documents, on 40 fact-recall questions built from our own corpus. Plain RAG won on every axis: 97.5% recall@5 against 60%, while injecting 15 times fewer tokens and running 17 times faster.

## What we did

Hindsight consolidates our fleet's history into a graph of facts, entities and temporal links, and a recall call returns the consolidated memories it judges relevant. The competing idea is dumber: keep the raw documents, build a search index, and return the top few chunks verbatim. The fair test is to give both the same knowledge and ask the same questions.

We pulled all 204 documents from our live `workloft` memory bank, about 245k characters of session summaries, and built the raw index over that exact text: a hybrid of BM25 and local MiniLM embeddings, 1,836 chunks, no API cost. For the benchmark we auto-generated 40 cloze questions, each blanking one distinctive fact that genuinely appears in the corpus (a project ref, a model id, a domain, a named tool) and that occurs in only a handful of documents. Then we scored both retrievers on identical questions with one metric: does the gold fact appear in the returned text. The whole thing ran in shadow mode against the recall HTTP endpoint. We changed nothing in the live memory path.

Method summary:

- Corpus: 204 documents from the live `workloft` bank, chunked into 1,836 three-sentence windows with one-sentence overlap.
- Raw RAG: BM25 (rank_bm25) + MiniLM (all-MiniLM-L6-v2) cosine, min-max normalised, equal-weight hybrid, top-5.
- Hindsight: `POST /memories/recall` at `budget=mid`, top-5 results for recall@5, full payload for the token measure.
- Metric: strict substring match of the gold fact in the returned text (verbatim survival), identical for both systems. 40 questions, seeded and deterministic.

## Why it was worth doing

The numbers were not close.

| Metric | Hindsight | Plain RAG |
|---|---|---|
| Recall@5 (top-5 items) | 60.0% | 97.5% |
| Recall, full payload | 72.5% | 97.5% |
| Mean tokens injected / recall | 3,799 | 246 |
| Mean latency / recall | 2.48s | 0.15s |
| Results returned / recall | ~97 | 5 |

Of Hindsight's 16 top-5 misses, 11 were absent from its entire payload: the fact had not survived consolidation in any retrievable form. Plain RAG got all 16 of those right. A Hindsight recall injects about 15 times more context for a lower hit rate. For a plain "what exactly did X say" lookup, consolidation here is paying a tax, not earning a discount.

## What's still off

This measures one axis: verbatim point-fact recall. A consolidated store does things raw retrieval cannot, like entity graphs, temporal ordering and cross-session synthesis, and those are exactly the "what is the shape of X over time" questions this benchmark does not ask. Some of the misses are also fair wording, not loss: a few golds were hyphenated phrasings (auto-kill, re-login) that consolidation would naturally reword, and our short-answer semantic check was too noisy to separate reword from loss cleanly, so treat 60% as a floor on strict recall rather than a verdict on everything Hindsight knows. We did not switch anything either. This was a shadow eval, by design, and the live memory path is untouched. The honest read: route verbatim lookups to raw RAG, keep consolidation for synthesis, and stop paying 15 times the tokens for the former.
