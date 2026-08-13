#!/usr/bin/env python3
"""
Worked example: a research agent has fetched a fan-out of documents for one
query. Before it carries them into an expensive multi-stage pipeline, run them
through early_prune and see what it keeps, what it drops and why, and how much
context never has to be paid for downstream.

Run:  python3 demo.py        (no arguments, no network, stdlib only)
"""

from early_prune import prune

QUERY = "how are teams cutting token cost in long-horizon research agents"

# A realistic fan-out: some on-topic, two near-duplicates of the same story from
# different sources, and two off-topic results the search engine dragged in.
DOCS = [
    # 0 — on topic, high value
    {"src": "arxiv.org", "text":
        "Pruning strategies applied at different pipeline stages reduce token "
        "usage and latency in long-horizon research agents. Pruning early, right "
        "after retrieval, yields the greatest efficiency gains because a document "
        "dropped early is not carried into any later stage."},
    # 1 — on topic
    {"src": "blog.eng.example", "text":
        "We cut our research agent's spend by trimming retrieved context before "
        "the synthesis step. Carrying every fetched page into the long-horizon "
        "loop was the single biggest driver of token cost across stages."},
    # 2 — near-duplicate of 1 (same story, syndicated on another site)
    {"src": "news.aggregator", "text":
        "We cut our research agent's spend by trimming retrieved context before "
        "the synthesis step. Carrying every fetched page into the long-horizon "
        "loop was the single biggest driver of token cost across the stages."},
    # 3 — on topic, model-routing angle
    {"src": "openrouter.ai", "text":
        "A cost-aware router sends cheap, mechanical agent sub-tasks to a small "
        "fast model and reserves the frontier model for orchestration, lowering "
        "operational token cost without changing the agent's behaviour."},
    # 4 — on topic but thin
    {"src": "forum.thread", "text":
        "Reducing token usage in agents mostly comes down to not stuffing the "
        "context window with things the model will never use."},
    # 5 — off topic (search noise)
    {"src": "recipes.example", "text":
        "The secret to an open crumb in a naturally leavened sourdough loaf is a "
        "high-hydration dough and a long cold fermentation in the fridge."},
    # 6 — on topic, caching angle
    {"src": "platform.docs", "text":
        "Prompt caching reuses the encoded prefix across calls, so repeated "
        "system and context tokens are billed at a large discount. For agents "
        "that reread the same long context each turn the saving compounds."},
    # 7 — near-duplicate of 0 (same paper, reworded abstract)
    {"src": "paperswithcode", "text":
        "This work shows that pruning at different pipeline stages reduces token "
        "usage and latency in long-horizon research agents, with early pruning "
        "after retrieval giving the greatest efficiency gains, since an early "
        "dropped document never reaches a later stage."},
    # 8 — off topic (search noise)
    {"src": "sports.example", "text":
        "The transfer window closed with three late signings, and the manager "
        "insisted the squad now has the depth to compete on four fronts."},
    # 9 — on topic, eval angle
    {"src": "eval.blog", "text":
        "Benchmark long-horizon agents on cost per solved task, not tokens per "
        "call. A cheaper per-call model that loops more can cost more per task."},
]


def bar(pct: float, width: int = 28) -> str:
    filled = round(width * pct / 100)
    return "#" * filled + "." * (width - filled)


def main() -> None:
    # Keep the on-topic, de-duplicated head that fits a 700-token budget.
    res = prune(QUERY, DOCS, token_budget=700, min_score=0.0, dedup=True)

    print(f"\nquery: {QUERY!r}\n")
    print(f"fetched {len(DOCS)} documents, ~{res.tokens_before} tokens (estimated)\n")

    print("scores (BM25-lite, higher = more relevant):")
    for i, d in enumerate(DOCS):
        print(f"  #{i:<2} {res.scores[i]:5.2f}  [{d['src']}]  {d['text'][:52]}...")
    print()

    print(f"KEPT {len(res.kept)} / {len(DOCS)}:")
    for d in res.kept:
        print(f"  + [{d['src']}] {d['text'][:60]}...")
    print()

    print(f"DROPPED {len(res.dropped)}:")
    for dp in res.dropped:
        print(f"  - #{dp.index:<2} {dp.reason:<11} {dp.detail}")
    print()

    print(f"tokens before : {res.tokens_before}")
    print(f"tokens after  : {res.tokens_after}")
    print(f"saved         : {res.tokens_before - res.tokens_after} "
          f"({res.pct_saved:.0f}%)  {bar(res.pct_saved)}")
    print()
    print("That saving is per downstream stage. A four-stage pipeline that would")
    print("have carried all ten docs into each stage now carries the kept head")
    print("into each, so the cut multiplies with pipeline depth.\n")


if __name__ == "__main__":
    main()
