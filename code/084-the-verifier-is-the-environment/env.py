"""
Agentic Environment Engineering — minimal reproduction.

Paper: "Agentic Environment Engineering for LLMs: A Survey of Environment
Modeling, Synthesis, Evaluation, and Application" (arXiv:2606.12191).

The survey names two synthesis paradigms (symbolic vs neural) and says each
needs its own evaluation, but quantifies neither. This module makes that
concrete on one cleanly-verifiable task domain: the Countdown numbers puzzle.

A task instance = (numbers: list[int], target: int). It is *valid* iff some
arithmetic expression over the numbers (using + - * /, each number at most
once, integer-only intermediate results) equals the target. The evaluation
harness here is a deterministic brute-force solver: ground truth, no model.
"""

from __future__ import annotations
from itertools import permutations, product
from functools import lru_cache
import json


# ---------------------------------------------------------------------------
# Evaluation harness — the deterministic oracle the paper never specifies.
# Brute-force solver over all orderings / operator choices for <= 6 numbers.
# Returns (solvable, min_ops) where min_ops is the *true* difficulty: the
# fewest binary operations any solution uses. Unsolvable -> (False, None).
# ---------------------------------------------------------------------------

OPS = [
    ("+", lambda a, b: a + b),
    ("-", lambda a, b: a - b),
    ("*", lambda a, b: a * b),
    ("/", lambda a, b: a // b if b != 0 and a % b == 0 else None),
]


def _combine(nums):
    """Every (value, ops) reachable by fully combining the multiset `nums`
    (uses ALL of nums). Memoised on the sorted tuple."""
    return _combine_cached(tuple(sorted(nums)))


@lru_cache(maxsize=None)
def _combine_cached(nums):
    if len(nums) == 1:
        return {(nums[0], 0)}
    out = set()
    n = len(nums)
    for mask in range(1, (1 << n) - 1):
        left = tuple(nums[i] for i in range(n) if mask & (1 << i))
        right = tuple(nums[i] for i in range(n) if not (mask & (1 << i)))
        if tuple(sorted(left)) > tuple(sorted(right)):
            continue  # de-dupe symmetric splits
        for lv, lo in _combine_cached(tuple(sorted(left))):
            for rv, ro in _combine_cached(tuple(sorted(right))):
                for _, fn in OPS:
                    for a, b in ((lv, rv), (rv, lv)):
                        v = fn(a, b)
                        if v is None:
                            continue
                        out.add((v, lo + ro + 1))
    return out


def _reachable(nums):
    """Standard Countdown rules: a solution may use ANY non-empty subset of
    the numbers, each at most once. Yields (value, ops) over all subsets."""
    n = len(nums)
    out = set()
    for mask in range(1, 1 << n):
        subset = tuple(nums[i] for i in range(n) if mask & (1 << i))
        out |= _combine(subset)
    return out


def solve(numbers, target):
    """Ground-truth oracle. Returns (solvable, min_ops) over subset solutions.
    min_ops == 0 means the target is simply one of the given numbers (a
    degenerate / trivially-easy 'puzzle')."""
    best = None
    for v, ops in _reachable(numbers):
        if v == target:
            best = ops if best is None else min(best, ops)
    return (best is not None), best


# ---------------------------------------------------------------------------
# Symbolic synthesis paradigm.
# Construct the answer first, read the task off it -> solvable by construction,
# difficulty is the operation count we chose. Diversity comes from the seed.
# ---------------------------------------------------------------------------

def _lcg(seed):
    """Tiny deterministic PRNG so the whole run is reproducible without
    importing random's global state (keeps numbers stable across machines)."""
    x = seed & 0xFFFFFFFF
    while True:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        yield x


def symbolic_synthesise(n_tasks, difficulty, seed=1):
    """difficulty = number of binary ops in the planted solution (>=1).

    We need difficulty+1 source numbers. Build a random expression tree over
    them, evaluate it to get a guaranteed-reachable target, emit the task.
    Rejects only when an intermediate division isn't integral (re-rolls).
    """
    rng = _lcg(seed)
    tasks = []
    k = difficulty + 1
    while len(tasks) < n_tasks:
        nums = [1 + next(rng) % 9 for _ in range(k)]  # numbers 1..9
        # fold left-to-right with random operators into one value
        acc = nums[0]
        ok = True
        for nxt in nums[1:]:
            _, fn = OPS[next(rng) % len(OPS)]
            a, b = (acc, nxt)
            v = fn(a, b)
            if v is None or v == a:  # skip non-integral div / trivial steps
                ok = False
                break
            acc = v
        if not ok or acc <= 0:
            continue
        tasks.append({"numbers": nums, "target": acc, "claimed_difficulty": difficulty})
    return tasks


def verified_synthesise(n_tasks, difficulty, seed=1):
    """Symbolic synthesis with the evaluation oracle IN THE LOOP: over-generate
    candidates and keep only those whose TRUE min-ops equals the target
    difficulty. This is the 'neural-symbolic' / verifier-gated paradigm — it
    shows the verifier, not the generator, is what makes difficulty controllable.
    """
    rng_seed = seed
    kept = []
    attempts = 0
    while len(kept) < n_tasks:
        cand = symbolic_synthesise(1, difficulty, seed=rng_seed)[0]
        rng_seed += 1
        attempts += 1
        ok, ops = solve(cand["numbers"], cand["target"])
        if ok and ops == difficulty:
            kept.append(cand)
        if attempts > n_tasks * 200:  # safety valve
            break
    return kept, attempts


if __name__ == "__main__":
    # smoke test the oracle + symbolic path
    ts = symbolic_synthesise(5, difficulty=3, seed=7)
    for t in ts:
        ok, ops = solve(t["numbers"], t["target"])
        print(t, "->", ok, ops)
        assert ok, "symbolic task must be solvable by construction"
    print("smoke ok")
