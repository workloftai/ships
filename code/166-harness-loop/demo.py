#!/usr/bin/env python3
"""
End to end demo of harness-loop on a real task with a real model.

The task: pull the UK postcode out of a line of text and return it in canonical
form (uppercase, one space before the final three characters). The agent is
Claude Haiku, deliberately the weak actor. The starting instruction is vague, so
Haiku fails a chunk of the cases, mostly on format.

The loop reads those failures, localises the culprit instruction, and proposes a
rewrite from the failing traces. We then re-run the same weak model with the
proposed instruction and measure the before and after. The model never changed.
Only the harness did.

Requires ANTHROPIC_API_KEY. Without it, run harness_loop.py directly against the
bundled example_failures.jsonl to see the localise-and-propose half.
"""
from __future__ import annotations
import json, os, re, sys, urllib.request, urllib.error
import harness_loop

EXECUTOR = "claude-haiku-4-5"  # the weak actor under test, on purpose

# (input line, canonical expected postcode)
CASES = [
    ("Please post it to 10 Downing Street, London sw1a 2aa", "SW1A 2AA"),
    ("Our registered office is at EC1A1BB.", "EC1A 1BB"),
    ("Deliveries to M1 1AE only after 9am", "M1 1AE"),
    ("She lives at 221b Baker Street, nw1 6xe", "NW1 6XE"),
    ("Invoice address: 1 St Aldates, Oxford OX11DP", "OX1 1DP"),
    ("The site is near CF10 1EP, right by the castle", "CF10 1EP"),
    ("Return to sender: LS2 7HY, Leeds", "LS2 7HY"),
    ("Head office b33 8th, Birmingham", "B33 8TH"),
    ("Meet me at the depot, g1 1xw", "G1 1XW"),
    ("Postal code is E20 2ST for the stadium", "E20 2ST"),
    ("Try the branch at TR26 1RT in St Ives", "TR26 1RT"),
    ("Files go to DL1 5TT, Darlington", "DL1 5TT"),
    ("Warehouse: pe12 6ab near the coast", "PE12 6AB"),
    ("The flat is at sw1w0ny, Belgravia", "SW1W 0NY"),
    ("Contact address BN1 1AA, Brighton seafront", "BN1 1AA"),
]


def ask(instruction, line):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({
        "model": EXECUTOR, "max_tokens": 40,
        "messages": [{"role": "user", "content": f"{instruction}\n\nText: {line}"}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    return "".join(b.get("text", "") for b in resp.get("content", [])).strip()


def score(instruction, label):
    rows, passed = [], 0
    for line, expected in CASES:
        got = " ".join(ask(instruction, line).split())  # collapse whitespace only
        ok = got == expected
        passed += ok
        rows.append({"instruction": "extract-postcode", "input": line,
                     "expected": expected, "got": got, "passed": ok})
        mark = "ok " if ok else "MISS"
        print(f"  [{mark}] {expected:9} <- {got!r}")
    print(f"{label}: {passed}/{len(CASES)} passed\n")
    return rows, passed


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY, or run harness_loop.py on example_failures.jsonl.")

    here = os.path.dirname(os.path.abspath(__file__))
    instr_dir = os.path.join(here, "instructions")
    out_dir = os.path.join(here, "proposals")

    v1 = harness_loop.load_instruction(instr_dir, "extract-postcode")
    print(f"instruction v1: {v1!r}\n")
    print("BEFORE — weak instruction:")
    rows, before = score(v1, "before")

    log_path = os.path.join(here, "run_failures.jsonl")
    with open(log_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print("running the loop (localise culprit, propose a rewrite from traces)...\n")
    traces = harness_loop.failing_traces(rows, "extract-postcode")
    proposal = harness_loop.propose(v1, traces)
    harness_loop.write_proposal(out_dir, "extract-postcode", v1, proposal, traces)
    v2 = proposal["revised_instruction"]
    print(f"proposed instruction v2 ({proposal['source']}):\n{v2!r}\n")

    print("AFTER — same model, proposed instruction:")
    _, after = score(v2, "after")

    print("=" * 48)
    print(f"model unchanged ({EXECUTOR}).")
    print(f"harness only: {before}/{len(CASES)} -> {after}/{len(CASES)} passed.")
    print("the rewrite is a proposal; a human accepts it before it goes live.")


if __name__ == "__main__":
    main()
