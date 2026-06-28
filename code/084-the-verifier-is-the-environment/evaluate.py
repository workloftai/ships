"""
Evaluation harness: score the symbolic and neural synthesis paradigms on the
three axes the survey names but never quantifies.

  validity     — fraction of emitted tasks that are actually solvable (oracle)
  calibration  — of the *solvable* tasks, fraction whose true min-ops matches
                 the claimed difficulty (3); plus the true-difficulty spread
  diversity    — distinct number-multisets / total (structural variety)

Run: python3 evaluate.py
"""

from __future__ import annotations
import json
from collections import Counter
from env import symbolic_synthesise, verified_synthesise, solve

CLAIMED = 3
N = 30


def score(tasks, name):
    solvable = 0
    calibrated = 0
    true_ops = []
    multisets = set()
    easier = 0    # solvable in fewer ops than claimed
    trivial = 0   # min_ops <= 1: target is a number or a single operation
    for t in tasks:
        ok, ops = solve(t["numbers"], t["target"])
        multisets.add(tuple(sorted(t["numbers"])))
        if ok:
            solvable += 1
            true_ops.append(ops)
            if ops == CLAIMED:
                calibrated += 1
            elif ops < CLAIMED:
                easier += 1
            if ops <= 1:
                trivial += 1
    n = len(tasks)
    spread = Counter(true_ops)
    # usable = solvable AND not a degenerate (>=2 op) puzzle
    usable = solvable - trivial
    return {
        "paradigm": name,
        "n": n,
        "validity": round(solvable / n, 3),
        "solvable": solvable,
        "usable": usable,
        "usable_rate": round(usable / n, 3),
        "diversity": round(len(multisets) / n, 3),
        "distinct_multisets": len(multisets),
        "difficulty_match_rate": round((calibrated / solvable) if solvable else 0.0, 3),
        "easier_than_claimed": easier,
        "trivial_min_ops_le_1": trivial,
        "true_min_ops_distribution": dict(sorted(spread.items())),
    }


def main():
    # Symbolic: ask for the same nominal difficulty (3 ops) the neural batch
    # was asked for, same count, so the comparison is apples-to-apples.
    sym = symbolic_synthesise(N, difficulty=CLAIMED, seed=20260628)
    ver, attempts = verified_synthesise(N, difficulty=CLAIMED, seed=20260628)
    with open("neural_batch.json") as f:
        neural = json.load(f)

    results = [
        score(sym, "symbolic"),
        score(neural, "neural"),
        {**score(ver, "verified_symbolic"), "candidates_drawn": attempts},
    ]
    print(json.dumps(results, indent=2))

    s, nresult, v = results
    print("\n--- headline ---")
    print(f"verifier-gated symbolic: difficulty match {v['difficulty_match_rate']:.0%} "
          f"from {v['candidates_drawn']} candidates drawn for {v['n']} kept.")
    print(f"validity:    symbolic {s['validity']:.0%}  vs  neural {nresult['validity']:.0%}")
    print(f"usable rate: symbolic {s['usable_rate']:.0%}  vs  neural {nresult['usable_rate']:.0%}  "
          f"(solvable AND not trivial)")
    print(f"diversity:   symbolic {s['diversity']:.0%}  vs  neural {nresult['diversity']:.0%}")
    print(f"difficulty match (true min-ops == claimed {CLAIMED}): "
          f"symbolic {s['difficulty_match_rate']:.0%}  vs  neural {nresult['difficulty_match_rate']:.0%}")
    invalid = nresult["n"] - nresult["solvable"]
    print(f"\nneural batch: {invalid}/{nresult['n']} unsolvable + "
          f"{nresult['trivial_min_ops_le_1']}/{nresult['n']} trivial "
          f"= {nresult['n'] - nresult['usable']}/{nresult['n']} a verifier must reject.")
    print(f"symbolic batch: {s['n'] - s['usable']}/{s['n']} rejected.")

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
