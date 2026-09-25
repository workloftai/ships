#!/usr/bin/env python3
"""
Bell state on IQM hardware (or IQM's noisy Garnet simulator).

Two qubits: Hadamard on q0, CNOT q0 -> q1, measure both. A perfect machine
returns only '00' and '11', about half each (the qubits are entangled, so they
always agree). Anything in '01' or '10' is hardware noise, which is the
interesting number.

  python3 bell.py                 # local noisy simulator (fake Garnet), free
  python3 bell.py --real garnet   # real QPU, needs IQM_TOKEN in .env next to this script
"""

import argparse
import json
import os
import time

from qiskit import QuantumCircuit, transpile

HERE = os.path.dirname(os.path.abspath(__file__))


def token():
    t = os.getenv("IQM_TOKEN")
    env = os.path.join(HERE, ".env")
    if not t and os.path.exists(env):
        for ln in open(env):
            if ln.startswith("IQM_TOKEN="):
                t = ln.split("=", 1)[1].strip()
    return t


def backend(real):
    if not real:
        from iqm.qiskit_iqm.fake_backends.fake_garnet import IQMFakeGarnet
        return IQMFakeGarnet(), "fake-garnet (local noisy simulator)"
    from iqm.qiskit_iqm import IQMProvider
    t = token()
    if not t:
        raise SystemExit("no IQM_TOKEN: put IQM_TOKEN=... in .env next to this script")
    return IQMProvider("https://resonance.iqm.tech/", quantum_computer=real,
                       token=t).get_backend(), f"{real} (real QPU)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=None, help="garnet | emerald | sirius")
    ap.add_argument("--shots", type=int, default=1000)
    a = ap.parse_args()

    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    be, label = backend(a.real)
    tqc = transpile(qc, backend=be, optimization_level=3)
    t0 = time.time()
    job = be.run(tqc, shots=a.shots)
    counts = job.result().get_counts()
    secs = round(time.time() - t0, 1)

    agree = counts.get("00", 0) + counts.get("11", 0)
    out = {"backend": label, "shots": a.shots, "counts": dict(sorted(counts.items())),
           "agree_pct": round(100 * agree / a.shots, 1),
           "noise_pct": round(100 * (a.shots - agree) / a.shots, 1),
           "wall_secs": secs, "job_id": str(getattr(job, "job_id", lambda: None)())}
    print(qc.draw(output="text"))
    print(json.dumps(out, indent=1))
    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    fn = os.path.join(HERE, "runs", f"bell-{'real-' + a.real if a.real else 'sim'}-{int(time.time())}.json")
    json.dump(out, open(fn, "w"), indent=1)
    print(f"saved {fn}")


if __name__ == "__main__":
    main()
