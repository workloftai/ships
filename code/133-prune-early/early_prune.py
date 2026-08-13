#!/usr/bin/env python3
"""
early_prune: drop the low-value tail of a research agent's context at the
earliest pipeline stage, before it is carried into any expensive model call.

The thesis, from "pruning strategies applied at different pipeline stages"
(arXiv 2608.08389): pruning at every stage helps, but *early* pruning helps most.
The reason is compounding. A long-horizon research agent fetches, then screens,
then synthesises, then writes. A junk document dropped at synthesis was still
paid for at every earlier stage that carried it. The same document dropped right
after fetch is paid for nowhere downstream. Early pruning removes a token from
every stage at once, so the saving multiplies with pipeline depth.

This module is that earliest stage. Given a query and the raw fetched documents,
it scores each for query relevance with a cheap lexical signal (BM25-lite, no
embeddings, no network), removes near-duplicate fetches, and drops the tail that
will not survive to the answer anyway. What comes out is a smaller set that costs
less at every stage that follows.

Zero dependencies, stdlib only. Token counts default to a chars/4 estimate; pass
your own `token_counter` (e.g. a real tokeniser) for exact figures.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Tokenisation (deliberately boring: lowercase word tokens, tiny stop list)
# ---------------------------------------------------------------------------
_WORD = re.compile(r"[a-z0-9]+")

# A short stop list so query scoring keys on content words, not glue. Kept
# small on purpose: an aggressive list throws away signal on technical queries.
_STOP = frozenset(
    "a an and are as at be by for from has have how in into is it its of on or "
    "that the this to was were what when which who why will with your you we our".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _est_tokens(text: str) -> int:
    """Rough token estimate. ~4 chars/token is the usual English heuristic."""
    return max(1, round(len(text) / 4))


# ---------------------------------------------------------------------------
# Public result shape
# ---------------------------------------------------------------------------
@dataclass
class Dropped:
    index: int          # position in the original input
    reason: str         # "off-topic" | "duplicate" | "over-budget"
    score: float
    tokens: int
    detail: str = ""    # e.g. "0.83 similar to kept #2"


@dataclass
class PruneResult:
    kept: list           # kept documents, in original input order, original shape
    dropped: list[Dropped] = field(default_factory=list)
    tokens_before: int = 0
    tokens_after: int = 0
    scores: list[float] = field(default_factory=list)  # score per original doc

    @property
    def pct_saved(self) -> float:
        if self.tokens_before <= 0:
            return 0.0
        return 100.0 * (self.tokens_before - self.tokens_after) / self.tokens_before


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _bm25_scores(query: str, doc_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """BM25 relevance of each doc to the query. Standard formula, stdlib only."""
    q_terms = set(_tokens(query))
    n = len(doc_tokens)
    if not q_terms or n == 0:
        return [0.0] * n

    # document frequency per query term
    df: dict[str, int] = {}
    for toks in doc_tokens:
        present = set(toks)
        for t in q_terms:
            if t in present:
                df[t] = df.get(t, 0) + 1

    avgdl = sum(len(t) for t in doc_tokens) / n or 1.0
    idf = {
        t: math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
        for t in q_terms
    }

    scores: list[float] = []
    for toks in doc_tokens:
        dl = len(toks) or 1
        tf: dict[str, int] = {}
        for w in toks:
            if w in q_terms:
                tf[w] = tf.get(w, 0) + 1
        s = 0.0
        for t in q_terms:
            f = tf.get(t, 0)
            if not f:
                continue
            s += idf[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


# ---------------------------------------------------------------------------
# Near-duplicate detection (word shingles + Jaccard)
# ---------------------------------------------------------------------------
def _shingles(toks: list[str], k: int = 8) -> frozenset[int]:
    if len(toks) < k:
        return frozenset({hash(tuple(toks))}) if toks else frozenset()
    return frozenset(hash(tuple(toks[i:i + k])) for i in range(len(toks) - k + 1))


def _jaccard(a: frozenset[int], b: frozenset[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


# ---------------------------------------------------------------------------
# The one entry point
# ---------------------------------------------------------------------------
def prune(
    query: str,
    docs: Iterable,
    *,
    token_budget: int | None = None,
    keep_ratio: float | None = None,
    min_score: float | None = 0.0,
    rel_floor: float | None = 0.15,
    dedup: bool = True,
    sim_threshold: float = 0.7,
    text_key: str = "text",
    token_counter: Callable[[str], int] | None = None,
) -> PruneResult:
    """Prune fetched documents down to the set worth carrying downstream.

    query          the research question the docs were fetched for.
    docs           list of strings, or dicts carrying text under `text_key`.
    token_budget   drop the lowest-scoring tail until the kept set fits this
                   many (estimated) tokens. None = no budget cap.
    keep_ratio     alternatively, keep only the top fraction by score (0..1).
    min_score      absolute score at or below which a doc is off-topic
                   (default 0.0 = only docs with zero query overlap).
    rel_floor      relative off-topic floor: a doc scoring below this fraction
                   of the top doc's score is off-topic. This is what catches
                   noise that overlaps the query on one incidental word. Both
                   floors are guarded: they never drop every doc, and the
                   top-scoring doc always survives (a query with no lexical
                   overlap keeps everything).
    dedup          remove near-duplicate fetches, keeping the higher-scored one.
    sim_threshold  Jaccard shingle similarity at/above which two docs are dupes.
    text_key       dict key holding the text when docs are dicts.
    token_counter  custom token counter; defaults to a chars/4 estimate.
    """
    docs = list(docs)
    count = _est_tokens if token_counter is None else token_counter

    def _text(d) -> str:
        if isinstance(d, dict):
            return str(d.get(text_key, ""))
        return str(d)

    texts = [_text(d) for d in docs]
    tokens_before = sum(count(t) for t in texts)
    n = len(docs)
    if n == 0:
        return PruneResult(kept=[], dropped=[], tokens_before=0, tokens_after=0, scores=[])

    doc_tokens = [_tokens(t) for t in texts]
    scores = _bm25_scores(query, doc_tokens)

    alive = list(range(n))
    dropped: list[Dropped] = []

    # 1. off-topic filter (guarded so it can never empty the set). A doc is
    #    off-topic if it falls below the absolute floor or below rel_floor of
    #    the top doc's score. The top doc always clears both, so `above` is
    #    never empty.
    max_s = max((scores[i] for i in alive), default=0.0)
    rel_thresh = rel_floor * max_s if (rel_floor is not None and max_s > 0) else None

    def _off_topic(i: int) -> bool:
        if min_score is not None and scores[i] <= min_score:
            return True
        if rel_thresh is not None and scores[i] < rel_thresh:
            return True
        return False

    if min_score is not None or rel_thresh is not None:
        above = [i for i in alive if not _off_topic(i)]
        if above and len(above) < len(alive):
            keep = set(above)
            for i in alive:
                if i not in keep:
                    dropped.append(Dropped(i, "off-topic", scores[i], count(texts[i])))
            alive = above

    # 2. near-duplicate removal, keeping the higher-scored of each pair
    if dedup and len(alive) > 1:
        order = sorted(alive, key=lambda i: scores[i], reverse=True)
        kept_shingles: list[tuple[int, frozenset[int]]] = []
        survivors: list[int] = []
        for i in order:
            sh = _shingles(doc_tokens[i])
            dup_of = None
            best_sim = 0.0
            for j, ksh in kept_shingles:
                sim = _jaccard(sh, ksh)
                if sim >= sim_threshold and sim > best_sim:
                    best_sim, dup_of = sim, j
            if dup_of is not None:
                dropped.append(Dropped(i, "duplicate", scores[i], count(texts[i]),
                                       f"{best_sim:.2f} similar to kept #{dup_of}"))
            else:
                kept_shingles.append((i, sh))
                survivors.append(i)
        alive = survivors

    # 3. budget / ratio cap: keep the highest-scoring head, drop the tail
    ranked = sorted(alive, key=lambda i: scores[i], reverse=True)
    if keep_ratio is not None:
        keep_n = max(1, math.ceil(keep_ratio * len(ranked)))
        for i in ranked[keep_n:]:
            dropped.append(Dropped(i, "over-budget", scores[i], count(texts[i]),
                                   f"below top {keep_ratio:.0%} by score"))
        ranked = ranked[:keep_n]
    if token_budget is not None:
        acc, keep_set = 0, []
        for i in ranked:
            tk = count(texts[i])
            if keep_set and acc + tk > token_budget:
                dropped.append(Dropped(i, "over-budget", scores[i], tk,
                                       f"would exceed {token_budget}-token budget"))
                continue
            acc += tk
            keep_set.append(i)
        ranked = keep_set

    kept_idx = set(ranked)
    kept = [docs[i] for i in range(n) if i in kept_idx]  # original order
    tokens_after = sum(count(texts[i]) for i in kept_idx)

    dropped.sort(key=lambda d: d.index)
    return PruneResult(
        kept=kept,
        dropped=dropped,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        scores=scores,
    )
