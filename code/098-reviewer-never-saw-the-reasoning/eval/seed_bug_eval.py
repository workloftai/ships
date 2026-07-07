#!/usr/bin/env python3
"""
seed_bug_eval.py - does the cross-lineage reviewer earn its cost?

Runs the Codex reviewer over samples with known seeded bugs and one clean
control, then scores it against ground truth (eval/BUGS.md):

    - catch rate:   seeded bugs it found
    - false rate:   HIGH/CRITICAL findings on the clean control (noise)
    - cost/latency: wall time and token spend per sample

The keyword match is a heuristic, not a judge. It makes the score reproducible;
confirm the misses by eye. The number that matters is not "did it find bugs" but
"did it beat a free second pass of the model that wrote the code". Record that
baseline (Claude self-review) in the same table before you trust the premium.

    python3 eval/seed_bug_eval.py            # runs Codex over every sample
    python3 eval/seed_bug_eval.py --json     # machine-readable

Needs the `codex` CLI authenticated (see the ship README). Each sample is one
`codex exec` call (~30-40s), so this is a minute or two. Run it detached.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (sample, list-of-seeded-bugs). Each bug: any of the keyword sets must all match
# somewhere in a finding's title+why for it to count as caught.
GROUND_TRUTH = {
    "orders.py": [
        {"name": "full-table load", "all": ["orders"],
         "any": ["entire", "all", "table", "memory", "scan"]},
        {"name": "float money", "all": [],
         "any": ["float", "cents", "rounding", "fractional"]},
    ],
    "auth.py": [
        {"name": "fail-open expiry", "all": [],
         "any": ["expiry", "expires", "expire", "never", "fail-open", "forever"]},
    ],
    "clean.py": [],  # control: any HIGH/CRITICAL finding is noise
}


def caught(bug, findings):
    for f in findings:
        blob = (f["title"] + " " + f["why"]).lower()
        if all(k in blob for k in bug["all"]) and (
            not bug["any"] or any(k in blob for k in bug["any"])
        ):
            return True
    return False


def review(sample_path):
    """Run the reviewer, return (findings, seconds)."""
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "codex_review.py"),
         "--path", sample_path, "--min-severity", "MEDIUM",
         "--min-confidence", "0.5", "--json"],
        capture_output=True, text=True,
    )
    secs = time.time() - t0
    try:
        return json.loads(proc.stdout)["findings"], secs
    except (json.JSONDecodeError, KeyError):
        sys.stderr.write(proc.stderr)
        return [], secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows, total_expected, total_caught, false_pos = [], 0, 0, 0
    for sample, bugs in GROUND_TRUTH.items():
        path = os.path.join(HERE, "samples", sample)
        findings, secs = review(path)
        highs = [f for f in findings
                 if f["severity"] in ("HIGH", "CRITICAL")]
        hits = [b["name"] for b in bugs if caught(b, findings)]
        total_expected += len(bugs)
        total_caught += len(hits)
        if not bugs:  # clean control
            false_pos += len(highs)
        rows.append({
            "sample": sample, "expected": len(bugs), "caught": len(hits),
            "caught_names": hits, "high_findings": len(highs),
            "seconds": round(secs, 1),
        })

    summary = {
        "catch_rate": f"{total_caught}/{total_expected}",
        "false_positives_on_clean": false_pos,
        "per_sample": rows,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print("Cross-lineage reviewer vs seeded bugs\n")
    for r in rows:
        tag = "control" if r["expected"] == 0 else f"{r['caught']}/{r['expected']}"
        names = (" " + ", ".join(r["caught_names"])) if r["caught_names"] else ""
        print(f"  {r['sample']:14} caught {tag:8} "
              f"({r['high_findings']} HIGH+, {r['seconds']}s){names}")
    print(f"\n  catch rate: {summary['catch_rate']}   "
          f"false positives on clean: {false_pos}")
    print("\n  Baseline to beat: a free second pass of the model that wrote the")
    print("  code. Fill that column in before you pay for the cross-lineage run.")


if __name__ == "__main__":
    main()
