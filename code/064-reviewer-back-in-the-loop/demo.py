"""demo — the proposer's best edit is a trap; the gate catches it.

Run:  python3 demo.py

Toy setup (deterministic, no model needed — the point is the control flow):

  * The harness has three knobs: retries, aggressive_cache, budget_ms.
  * The proposer sees a "dev" task set. On it, turning on aggressive_cache is
    the single biggest win — it drops latency so slow tasks fit the budget.
  * The gate holds a private "held-out" set that includes freshness-sensitive
    tasks. aggressive_cache serves them stale data, so it REGRESSES held-out.
  * A plain retries bump is the honest edit: it helps flaky tasks on both sets.

A naive Self-Harness loop trusts the proposer's own number and ships the cache
edit. The governed loop recomputes on held-out, rejects the cache edit, accepts
the retries edit, and records both — accept and reject — in a tamper-evident log.
"""
from __future__ import annotations

from harness_gate import (
    ChangeLog, GovernedLoop, HarnessEdit, Proposer, ReviewGate, score,
)


def make_task(base_latency: int, requires_fresh: bool, flaky: bool,
              needed_retries: int = 3):
    """Return a task scorer closing over its own requirements."""
    def task(h) -> bool:
        latency = base_latency - (400 if h.get("aggressive_cache") else 0)
        within_budget = latency <= h.get("budget_ms", 1000)
        flaky_ok = (not flaky) or h.get("retries", 1) >= needed_retries
        fresh_ok = (not requires_fresh) or (not h.get("aggressive_cache"))
        return within_budget and flaky_ok and fresh_ok
    return task


# Dev set the proposer can see: cache flips the slow tasks from fail -> pass.
DEV = [
    make_task(1300, requires_fresh=False, flaky=False),
    make_task(1300, requires_fresh=False, flaky=False),
    make_task(1300, requires_fresh=False, flaky=False),
    make_task(500, requires_fresh=False, flaky=True),
    make_task(500, requires_fresh=False, flaky=True),
]

# Held-out set the proposer never sees: cache BREAKS the fresh-sensitive tasks.
HELD_OUT = [
    make_task(600, requires_fresh=True, flaky=False),
    make_task(600, requires_fresh=True, flaky=False),
    make_task(1300, requires_fresh=False, flaky=False),
    make_task(500, requires_fresh=False, flaky=True),
    make_task(500, requires_fresh=False, flaky=True),
]

CANDIDATES = [
    HarnessEdit("enable aggressive_cache (cut latency)", {"aggressive_cache": True}, 0.0),
    HarnessEdit("raise retries 1 -> 3 (de-flake)", {"retries": 3}, 0.0),
]


def bar(label: str, value: float) -> str:
    return f"{label:>10}: {'#' * round(value * 20):<20} {value:.2f}"


def main() -> None:
    harness = {"retries": 1, "aggressive_cache": False, "budget_ms": 1000}

    proposer = Proposer(DEV, CANDIDATES)
    gate = ReviewGate(HELD_OUT, floor=0.0)
    loop = GovernedLoop(harness=harness, proposer=proposer, gate=gate)

    print("=" * 64)
    print("  SELF-IMPROVING HARNESS, WITH THE REVIEWER PUT BACK IN")
    print("=" * 64)
    print(bar("dev", score(harness, DEV)))
    print(bar("held-out", score(harness, HELD_OUT)))
    print()

    ranked = proposer.propose(harness)
    print("Proposer's ranking (on the dev set it can see):")
    for e in ranked:
        print(f"  +{e.claimed_delta:.2f} dev   {e.description}")
    print(f"\n  -> A naive Self-Harness loop ships the #1: \"{ranked[0].description}\"")
    print("     It trusts the proposer's own regression test. Watch the gate.\n")

    verdicts = loop.step()
    print("Independent gate verdicts (recomputed on the held-out set):")
    for v in verdicts:
        tag = "ACCEPT" if v.accepted else "REJECT"
        print(f"  [{tag}] {v.edit.description}")
        print(f"           claimed +{v.edit.claimed_delta:.2f} dev | "
              f"held-out {v.held_out_before:.2f} -> {v.held_out_after:.2f} | {v.reason}")
    print()

    print(f"Final harness: {loop.harness}")
    print(bar("dev", score(loop.harness, DEV)))
    print(bar("held-out", score(loop.harness, HELD_OUT)))
    print("  The trap edit (proposer's #1) was refused; the honest edit landed.\n")

    print("-" * 64)
    print("  TAMPER-EVIDENT CHANGE LOG")
    print("-" * 64)
    for e in loop.log.entries:
        print(f"  #{e.index} v{e.harness_version} "
              f"{'ACCEPTED' if e.accepted else 'REJECTED':>8}  "
              f"{e.edit_description}")
        print(f"        hash {e.entry_hash[:16]}…  prev {e.prev_hash[:8]}…")
    print(f"\n  chain verifies: {loop.log.verify()}")

    # Now forge the record: pretend the rejected cache edit was accepted.
    forged = loop.log.entries[0]
    forged.accepted = True
    print(f"  tamper with entry #0 (flip REJECTED -> ACCEPTED)…")
    print(f"  chain verifies: {loop.log.verify()}   <- break is detected")
    print("=" * 64)


if __name__ == "__main__":
    main()
