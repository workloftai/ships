#!/usr/bin/env python3
"""
Tests for early_prune. No network, stdlib only.  Run:  python3 test_early_prune.py
"""

from early_prune import prune, _bm25_scores, _tokens, _jaccard, _shingles

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def main() -> None:
    q = "token cost in long-horizon agents"

    # 1. empty input is safe
    r = prune(q, [])
    check("empty input returns empty result", r.kept == [] and r.tokens_before == 0)

    # 2. single doc is always kept
    r = prune(q, ["cutting token cost in long-horizon agents"])
    check("single doc kept", len(r.kept) == 1)

    # 3. relevant scores above off-topic
    docs = [
        "cutting token cost in long-horizon research agents by pruning context",
        "a sourdough loaf needs a long cold fermentation for an open crumb",
    ]
    s = _bm25_scores(q, [_tokens(d) for d in docs])
    check("relevant scores higher than off-topic", s[0] > s[1])

    # 4. off-topic dropped, on-topic kept (guarded min_score)
    r = prune(q, docs, dedup=False)
    check("off-topic dropped", any(d.reason == "off-topic" for d in r.dropped))
    check("on-topic kept", docs[0] in r.kept)

    # 5. min_score never empties the set even if nothing overlaps the query
    off = ["completely unrelated text one", "completely unrelated text two"]
    r = prune("xyzzy plugh", off)
    check("no-overlap query keeps everything", len(r.kept) == 2)

    # 6. near-duplicates collapse to one (realistic syndicated-story length)
    a = ("We cut our research agent's spend by trimming retrieved context before "
         "the synthesis step. Carrying every fetched page into the long-horizon "
         "loop was the single biggest driver of token cost across all the stages.")
    b = ("We cut our research agent's spend by trimming retrieved context before "
         "the synthesis step. Carrying every fetched page into the long-horizon "
         "loop was the single biggest driver of token cost across the stages.")
    r = prune("trimming retrieved context", [a, b], min_score=None, rel_floor=None)
    check("near-duplicate collapsed", len(r.kept) == 1)
    check("duplicate reason recorded", any(d.reason == "duplicate" for d in r.dropped))

    # 7. jaccard sanity
    check("identical shingles jaccard 1.0",
          _jaccard(_shingles(_tokens(a)), _shingles(_tokens(a))) == 1.0)

    # 8. token budget caps the kept set and reports the saving
    many = [f"token cost long-horizon agents variant number {i} " * 6 for i in range(10)]
    r = prune(q, many, token_budget=200, dedup=False, min_score=None)
    check("budget caps tokens", r.tokens_after <= 200 + 60)  # +one doc slack
    check("budget dropped the tail", any(d.reason == "over-budget" for d in r.dropped))
    check("saving is positive", r.pct_saved > 0)

    # 9. keep_ratio keeps the top fraction
    r = prune(q, many, keep_ratio=0.3, dedup=False, min_score=None)
    check("keep_ratio ~30% of 10 -> 3", len(r.kept) == 3)

    # 10. dict docs supported, original order preserved
    dd = [{"text": docs[0], "src": "x"}, {"text": docs[1], "src": "y"}]
    r = prune(q, dd, dedup=False)
    check("dict docs kept as dicts", all(isinstance(d, dict) for d in r.kept))

    # 11. custom token_counter honoured
    r = prune(q, ["some text here"], token_counter=lambda t: 999)
    check("custom token_counter used", r.tokens_before == 999)

    # 12. tokens_after never exceeds tokens_before
    r = prune(q, docs)
    check("after <= before", r.tokens_after <= r.tokens_before)

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
