"""demo.py — measure the token delta on a real trajectory over real files.

Run:  python3 demo.py

Replays one fixed coding-agent trajectory (reproduce a failing test, search the
codebase, read a large module, re-check the log, fix and verify, answer) over
the real files in sample_repo/. Counts cumulative input tokens with tiktoken,
naive vs SoL-Pi, does a leave-one-out per mechanism, and proves every piece of
evidence the answer depends on is still retrievable byte-exact.

No model is called. The number is ours, on this trajectory, not the paper's.
"""
from __future__ import annotations

from pathlib import Path

import harness
import solpi
from harness import Step, run

REPO = Path(__file__).parent / "sample_repo"
ILLUSTRATIVE_RATE = 1.25  # $ per 1M input tokens, for a cost line only


def load(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8", errors="replace")


def build_trajectory() -> list[Step]:
    build_log = load("build.log")
    big_module = load("big_module.py")
    grep = load("grep_results.txt")
    widget = load("widget.py")
    small = "grep -n apply_discount widget.py\n5:def apply_discount(price, pct):\n"
    reason = "Hypothesis: apply_discount dropped the /100. Checking callers next.\n"
    region = ("def push_draft_from_disk(channel, slug, *, publish_at=None,\n"
              "        with_hero=True):\n    ...\n")  # a small, targeted re-read
    return [
        # subtask 0: reproduce the failure (log stays live for a couple of turns)
        Step("tool", "log", "python3 -m unittest -v test_widget", build_log, subtask=0),
        Step("tool", "grep", "grep -rn 'def apply_discount' .", small, subtask=0),
        Step("tool", "note", "reason about the failure", reason, subtask=0),
        Step("boundary", subtask_done=0),
        # subtask 1: locate the symbol across the codebase (big reads, then more work)
        Step("tool", "grep", "grep -rn 'def ' scripts/ labs.html", grep, subtask=1),
        Step("tool", "file", "cat big_module.py", big_module, subtask=1),
        Step("tool", "note", "trace the discount path", reason, subtask=1),
        Step("tool", "file", "sed -n '110,140p' big_module.py", region, subtask=1),
        Step("tool", "file", "cat widget.py", widget, subtask=1),
        Step("boundary", subtask_done=1),
        # subtask 2: re-check the exact assertion in the archived log (retrieval)
        Step("reopen", ref=0),
        Step("tool", "note", "re-read failing assertion", "confirmed: -900 != 90\n", subtask=2),
        Step("boundary", subtask_done=2),
        # subtask 3: fix and verify in one fused action
        Step("edit_verify", command="edit widget.py && python3 -m unittest -v test_widget",
             text=("applied fix to apply_discount (divide pct by 100)\n"
                   "test_no_discount ... ok\ntest_discount_applies ... ok\n"
                   "test_line_total ... ok\nRan 3 tests OK\n"),
             subtask=3),
        Step("answer"),
    ]


def evidence_retrievable(result: dict, needles: list[str]) -> list[tuple[str, bool]]:
    """Every needle must survive byte-exact in some archived observation."""
    archive = "\n".join(o.full_text for o in result["observations"])
    return [(n, n in archive) for n in needles]


def fmt(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    traj = build_trajectory()

    naive = run(traj, "naive")
    solpi_full = run(traj, "solpi")

    base = naive["cum_input_tokens"]
    full = solpi_full["cum_input_tokens"]
    saved = base - full
    pct = 100 * saved / base

    print("=" * 68)
    print("SoL-Pi harness spike — cumulative INPUT tokens over one trajectory")
    print("real files:  build.log, big_module.py, grep_results.txt, widget.py")
    print("tokenizer:   tiktoken o200k_base (GPT-4o / 5 family)")
    print("=" * 68)
    print(f"  naive  : {fmt(base):>12} tokens over {naive['requests']} requests")
    print(f"  SoL-Pi : {fmt(full):>12} tokens over {solpi_full['requests']} requests")
    print(f"  saved  : {fmt(saved):>12} tokens   ({pct:.1f}% reduction)")
    print(f"  cost   : ${base/1e6*ILLUSTRATIVE_RATE:.4f} -> "
          f"${full/1e6*ILLUSTRATIVE_RATE:.4f}  (list price, NO cache; see caveats)")
    print(f"  ratio  : naive sends {base/full:.1f}x the input tokens SoL-Pi does")
    print("  baseline note: naive = re-send everything, zero context management.")
    print()

    # cumulative build-up: switch mechanisms on one at a time, in cost order
    print("cumulative build-up (each row adds one mechanism on top of the last):")

    def measure(**kw) -> int:
        old_p, old_r = solpi.PACK_THRESHOLD, solpi.REDUCE_THRESHOLD
        if kw.pop("no_pack", False):
            solpi.PACK_THRESHOLD = 10**12
        if kw.pop("no_reduce", False):
            solpi.REDUCE_THRESHOLD = 10**12
        out = run(traj, "solpi", **kw)["cum_input_tokens"]
        solpi.PACK_THRESHOLD, solpi.REDUCE_THRESHOLD = old_p, old_r
        return out

    ladder = [
        ("naive (no management)", base),
        ("+ ObservationPack", measure(no_reduce=True, compact_on=False, fuse=False)),
        ("+ Evidence Reducer", measure(compact_on=False, fuse=False)),
        ("+ Online Context Compact", measure(fuse=False)),
        ("+ Action Fusion (= SoL-Pi)", full),
    ]
    prev = None
    for name, cost in ladder:
        delta = "" if prev is None else f"  (-{fmt(prev-cost)})"
        print(f"  {name:<28} {fmt(cost):>10} tokens  ({100*cost/base:.1f}% of naive){delta}")
        prev = cost
    print()

    # correctness: no evidence is lost, only deferred behind a handle
    needles = [
        "test_discount_applies",          # the failing test
        "AssertionError: -900 != 90",     # the exact failure
        "apply_discount",                 # the buggy function
        "push_draft_from_disk",           # a real symbol in the large module
    ]
    checks = evidence_retrievable(solpi_full, needles)
    ok = all(present for _, present in checks)
    print("evidence retrievability (byte-exact in the archive behind a handle):")
    for needle, present in checks:
        print(f"  [{'OK ' if present else 'LOST'}] {needle}")
    print()
    print(f"RESULT: {pct:.1f}% fewer input tokens, "
          f"{'all evidence retrievable' if ok else 'EVIDENCE LOST'}.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
