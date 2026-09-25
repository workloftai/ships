# 174 · First circuits on real quantum hardware

Two small, honest experiments on IQM's superconducting quantum computers via
the free IQM Resonance tier, written with Claude Code by people who are not
physicists. Every result is graded against a known right answer.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python bell.py                        # noisy local simulator, free
.venv/bin/python qaoa_maxcut.py                 # tune + simulator
echo "IQM_TOKEN=..." > .env && chmod 600 .env   # token: Resonance > Profile > Access tokens
.venv/bin/python bell.py --real garnet          # real QPU (garnet | emerald | sirius)
.venv/bin/python qaoa_maxcut.py --real garnet
```

## 1. Bell state (`bell.py`)

Two entangled qubits, 1000 shots. A perfect machine only ever returns `00` or
`11`. Anything else is noise.

| backend | 00 | 11 | 01 | 10 | agree | noise |
|---|---|---|---|---|---|---|
| IQM fake-Garnet (noisy simulator) | 514 | 432 | 35 | 19 | 94.6% | 5.4% |
| **Garnet, 20 qubits (real)** | 513 | 472 | 5 | 10 | **98.5%** | **1.5%** |
| **Emerald, 54 qubits (real)** | 470 | 510 | 8 | 12 | **98.0%** | **2.0%** |

The real chips were cleaner than the bundled simulator of them: the fake
backend's error profile is more pessimistic than the machines' current
calibration.

## 2. Toy QAOA max-cut (`qaoa_maxcut.py`)

5 nodes, 6 edges (a ring plus one chord). Max cut is 5; 4 of the 32 possible
splits achieve it. One-layer QAOA, two angles tuned on an exact classical
simulation, then run once. 2000 shots.

| | expected cut | approx. ratio | shots that were optimal |
|---|---|---|---|
| random guessing | 3.00 | 0.600 | 12.5% |
| ideal noiseless QAOA (ceiling) | 4.11 | 0.822 | |
| fake-Garnet simulator | 3.94 | 0.788 | 36.8% |
| **Garnet (real)** | **3.96** | **0.791** | **37.6%** |

The machine's four most frequent answers were exactly the four optimal cuts.

## What this is not

A speed-up. A laptop solves this max-cut instantly by trying all 32 options.
This is a worked, graded example of the workflow: tune classically, run once
on hardware, check against ground truth. Raw results are in `runs/`.
