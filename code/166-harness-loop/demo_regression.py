#!/usr/bin/env python3
"""
The regression guard (v2), shown catching a real over-correction.

Tonight's first demo left one honest gap: the loop proposed a rewrite but never
checked it left the already-passing cases alone. This closes it.

Same postcode task, but a starting instruction that only half fails: it uppercases
but never inserts the missing space, so the cases whose text already has a space
pass, and the run-together ones fail. The loop proposes a fix from the failures.
Then the guard re-runs that fix against every case that already passed, and only
blesses it if none of them break.

To show the guard earning its place, we also run a plausible but naive candidate:
"put the space after the fourth character." It fixes the failures it was shown
(all four-character outward codes) and quietly breaks the short ones it never saw
fail. The guard catches exactly that.

Requires ANTHROPIC_API_KEY.
"""
from __future__ import annotations
import json, os, sys, urllib.request
import harness_loop

EXECUTOR = "claude-haiku-4-5"

# text line -> canonical postcode. Some already have a space (v1 passes these),
# some are run together (v1 fails these).
CASES = [
    ("London sw1a 2aa",        "SW1A 2AA"),   # spaced
    ("depot m1 1ae",           "M1 1AE"),     # spaced, short outward code
    ("castle cf10 1ep",        "CF10 1EP"),   # spaced
    ("Leeds ls2 7hy",          "LS2 7HY"),    # spaced
    ("seafront bn1 1aa",       "BN1 1AA"),    # spaced
    ("stadium e20 2st",        "E20 2ST"),    # spaced, short outward code
    ("office EC1A1BB",         "EC1A 1BB"),   # run together, 4-char outward
    ("Oxford OX11DP",          "OX1 1DP"),    # run together
    ("Birmingham b338th",      "B33 8TH"),    # run together
    ("Belgravia sw1w0ny",      "SW1W 0NY"),   # run together, 4-char outward
    ("coast pe126ab",          "PE12 6AB"),   # run together, 4-char outward
]

V1 = "Return the postcode from the text in uppercase, with nothing else."

# A plausible fix that over-fits the failures it was shown (all 4-char outward
# codes) and breaks the short ones. This is the mistake the guard exists to catch.
NAIVE = ("Return the postcode in uppercase and nothing else. Remove any spaces, "
         "then put a single space after the fourth character.")


def ask(instruction, line):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({"model": EXECUTOR, "max_tokens": 40,
        "messages": [{"role": "user", "content": f"{instruction}\n\nText: {line}"}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    return "".join(b.get("text", "") for b in resp.get("content", [])).strip()


def score(instruction):
    rows = []
    for line, expected in CASES:
        got = " ".join(ask(instruction, line).split())
        rows.append({"instruction": "extract-postcode", "input": line,
                     "expected": expected, "got": got, "passed": got == expected})
    return rows


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY.")

    print(f"instruction v1: {V1!r}\n")
    rows = score(V1)
    passers = harness_loop.passing_cases(rows, "extract-postcode")
    failers = harness_loop.failing_traces(rows, "extract-postcode")
    print(f"v1 score: {len(passers)}/{len(CASES)} pass, {len(failers)} fail")
    print(f"  already passing (must not break): {[p['expected'] for p in passers]}")
    print(f"  failing (to fix):                {[f['expected'] for f in failers]}\n")

    print("loop proposes a rewrite from the failing traces...")
    proposal = harness_loop.propose(V1, failers)
    v2 = proposal["revised_instruction"]
    print(f"proposed v2 ({proposal['source']}):\n  {v2!r}\n")

    print("regression guard: re-running the proposal against the passing cases...")
    reg = harness_loop.verify_rewrite(v2, passers, ask)
    print(f"  proposal regressions: {len(reg)} -> "
          f"{'SAFE, accept' if not reg else 'NEEDS REVISION'}\n")

    print("for contrast, a plausible but naive candidate:")
    print(f"  {NAIVE!r}")
    reg2 = harness_loop.verify_rewrite(NAIVE, passers, ask)
    print(f"  naive-candidate regressions: {len(reg2)}")
    for r in reg2:
        print(f"    [BROKE] {r['expected']:9} became {r['got']!r}")
    print(f"  verdict: {'SAFE' if not reg2 else 'REFUSED, the guard caught the over-correction'}\n")

    print("=" * 56)
    print(f"the loop's own proposal: SAFE ({len(reg)} regressions).")
    print(f"the naive over-fit:      REFUSED ({len(reg2)} regressions caught).")
    print("a rewrite is only blessed if nothing that already worked breaks.")


if __name__ == "__main__":
    main()
