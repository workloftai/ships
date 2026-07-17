#!/usr/bin/env python3
"""End-to-end demo of the deepfix loop, reproducible offline.

The scenario is real and taken from our own fleet: an agent given a global rule
("never use `any`") wastes a whole reasoning step trying to enforce that
TypeScript rule inside a *markdown* file, where it does not apply. A human edits
that one step. deepfix then distils the edit into a standing directive and shows
what carrying that fix costs, inline every run versus distilled once.

Run offline (no model, honest about no compression):
    python3 demo.py

Run the real distillation step against Claude (needs ANTHROPIC_API_KEY):
    python3 demo.py --llm
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import deepfix

HERE = Path(__file__).parent
RULE = "-" * 68


def banner(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="distil with a real Claude call")
    args = ap.parse_args()

    trace = deepfix.Trace.load(HERE / "trace_example.json")

    banner("1. THE RUN THAT WENT WRONG")
    print(f"Task: {trace.task}\n")
    for s in trace.steps:
        marker = "  <-- wrong turn" if s["id"] == 2 else ""
        print(f"  step {s['id']}: {s['thought'][:90]}...{marker}")

    banner("2. HUMAN EDITS THE ONE BAD STEP")
    fixed = (
        "The no-`any` rule targets TypeScript source, not this markdown plan. "
        "It does not apply here, so I will not spend a pass enforcing it. "
        "I will just write the plan."
    )
    corr = deepfix.edit(trace, step_id=2, corrected=fixed)
    print(f"before: {corr.before[:110]}...")
    print(f"after : {corr.after}")

    banner("3. DISTIL THE EDIT INTO A REUSABLE DIRECTIVE")
    directive = deepfix.distil(corr, use_llm=args.llm)
    if directive.verbatim:
        print("(no model: stored verbatim, so there is no compression)")
    else:
        print("(distilled by Claude)")
    print(f"directive: {directive.rule}")

    banner("4. WHAT THE FIX COSTS, INLINE EVERY RUN VS DISTILLED ONCE")
    c = deepfix.cost(corr, directive, runs=100)
    approx = "" if c["exact_tokeniser"] else "  (approx, install tiktoken for exact)"
    print(f"inline fix per run : {c['inline_tokens_per_run']} tokens{approx}")
    print(f"distilled per run  : {c['directive_tokens_per_run']} tokens")
    print(f"saved per run      : {c['saved_per_run']} tokens ({c['saved_pct']}%)")
    print(f"saved over 100 runs: {c['saved_over_runs']} tokens")
    if c["verbatim_directive"]:
        print("\nThe offline path proves the mechanism, not the saving: without a model")
        print("the directive is the full correction, so it saves nothing. Re-run with")
        print("--llm to see the rule compress and the saving become real.")

    banner("5. THE NEXT RUN CARRIES THE RULE, NOT THE STORY")
    composed = deepfix.apply("Write a markdown plan for the notifications service.", [directive])
    print(composed)


if __name__ == "__main__":
    main()
