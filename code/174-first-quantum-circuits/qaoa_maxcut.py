#!/usr/bin/env python3
"""
Toy QAOA max-cut on a 5-node graph, tuned on a laptop-grade simulator, then
run once on real IQM hardware.

Max-cut: split the nodes into two groups so that as many edges as possible
cross between the groups. With 5 nodes there are only 32 ways to split them, so
we can brute-force the true answer and grade the quantum run honestly.

QAOA (p=1): put every qubit in superposition, apply one "cost" layer that
rewards cut edges (angle gamma) and one "mixer" layer (angle beta), measure.
The two angles are tuned classically on an exact simulator, then the tuned
circuit runs on the QPU.

Scores reported for each backend:
  expected_cut   average cut size over all shots
  approx_ratio   expected_cut / best possible cut
  p_optimal      share of shots that were an optimal cut
Baseline: random guessing gives expected cut = edges / 2.

  python3 qaoa_maxcut.py                 # tune + noisy simulator only
  python3 qaoa_maxcut.py --real garnet   # tune + simulator + one real QPU run
"""

import argparse
import itertools
import json
import os
import time

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

from bell import backend

N = 5
EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)]  # a ring plus one chord


def cut_size(bits):
    """bits[i] is node i's side."""
    return sum(bits[a] != bits[b] for a, b in EDGES)


def bits_of(key):
    """Qiskit keys are little-endian: the rightmost character is qubit 0."""
    return [int(c) for c in reversed(key)]


def circuit(gamma, beta, measure=True):
    qc = QuantumCircuit(N, N if measure else 0)
    qc.h(range(N))
    for a, b in EDGES:
        qc.rzz(2 * gamma, a, b)
    qc.rx(2 * beta, range(N))
    if measure:
        qc.measure(range(N), range(N))
    return qc


def exact_expectation(gamma, beta):
    probs = Statevector(circuit(gamma, beta, measure=False)).probabilities_dict()
    return sum(p * cut_size(bits_of(k)) for k, p in probs.items())


def score(counts, best):
    shots = sum(counts.values())
    exp = sum(n * cut_size(bits_of(k)) for k, n in counts.items()) / shots
    p_opt = sum(n for k, n in counts.items() if cut_size(bits_of(k)) == best) / shots
    return {"expected_cut": round(exp, 3), "approx_ratio": round(exp / best, 3),
            "p_optimal": round(p_opt, 3)}


def run(be, qc, shots):
    t0 = time.time()
    job = be.run(transpile(qc, backend=be, optimization_level=3), shots=shots)
    counts = job.result().get_counts()
    return counts, round(time.time() - t0, 1), str(job.job_id())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=None)
    ap.add_argument("--shots", type=int, default=2000)
    a = ap.parse_args()

    # 1. brute-force ground truth
    cuts = {"".join(map(str, b)): cut_size(b) for b in itertools.product([0, 1], repeat=N)}
    best = max(cuts.values())
    optimal = sorted(k for k, v in cuts.items() if v == best)
    uniform = sum(cuts.values()) / len(cuts)
    p_opt_random = len(optimal) / len(cuts)
    print(f"graph: {N} nodes, {len(EDGES)} edges; max cut = {best}, "
          f"{len(optimal)} optimal splits of {len(cuts)}")
    print(f"random guessing: expected cut {uniform:.2f} (ratio {uniform / best:.3f}), "
          f"p_optimal {p_opt_random:.3f}")

    # 2. tune the two angles classically (exact simulation, 40x40 grid)
    grid = np.linspace(0, np.pi, 40)
    g, b = max(itertools.product(grid, grid / 2), key=lambda gb: exact_expectation(*gb))
    ideal = exact_expectation(g, b)
    print(f"tuned: gamma={g:.3f} beta={b:.3f}, ideal expected cut {ideal:.3f} "
          f"(ratio {ideal / best:.3f})")

    qc = circuit(g, b)
    results = {"graph": {"nodes": N, "edges": EDGES, "max_cut": best, "optimal": optimal},
               "random": {"expected_cut": round(uniform, 3),
                          "approx_ratio": round(uniform / best, 3),
                          "p_optimal": round(p_opt_random, 3)},
               "tuned": {"gamma": round(float(g), 4), "beta": round(float(b), 4),
                         "ideal_expected_cut": round(ideal, 3),
                         "ideal_ratio": round(ideal / best, 3)}}

    # 3. noisy simulator, then (optionally) the real machine
    targets = [None] + ([a.real] if a.real else [])
    for t in targets:
        be, label = backend(t)
        counts, secs, jid = run(be, qc, a.shots)
        s = score(counts, best)
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
        results[label] = {**s, "wall_secs": secs, "job_id": jid,
                          "top5": [(k, n, cut_size(bits_of(k))) for k, n in top]}
        print(f"{label}: expected cut {s['expected_cut']} (ratio {s['approx_ratio']}), "
              f"p_optimal {s['p_optimal']}, {secs}s")

    os.makedirs("runs", exist_ok=True)
    fn = f"runs/qaoa-{'real-' + a.real if a.real else 'sim'}-{int(time.time())}.json"
    json.dump(results, open(fn, "w"), indent=1)
    print(f"saved {fn}")


if __name__ == "__main__":
    main()
