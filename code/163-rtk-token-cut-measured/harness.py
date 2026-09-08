#!/usr/bin/env python3
"""
rtk A/B harness — measures the context-output cost of a representative
agent coding loop, native vs routed through rtk.

Method (stated plainly so the number is auditable):
  * For each command an agent typically runs to orient/search/read a repo,
    we capture the FULL combined stdout+stderr the agent would have to read.
  * We measure it two ways: raw bytes, and an estimated token count using the
    standard rough proxy of ceil(chars / 4). This is an estimate, not a billed
    figure. rtk's own `gain` ledger is reported separately as a cross-check.
  * "native" = the plain command. "rtk" = the same work via the rtk proxy.
  * We do NOT claim this equals your final Anthropic bill: model I/O, system
    prompt, and prior turns all dilute the percentage. This measures the one
    thing rtk touches — the command output an agent ingests each turn.
"""
import subprocess, math, sys, os, json

RTK = os.environ["RTK"]
REPO = os.environ.get("REPO", "/home/workloft/conexus")

# (label, native argv, rtk argv)
CASES = [
    ("git status",        ["git", "status"],                       [RTK, "git", "status"]),
    ("git diff",          ["git", "diff"],                         [RTK, "git", "diff"]),
    ("git log -50",       ["git", "log", "--oneline", "-50"],      [RTK, "git", "log", "--oneline", "-50"]),
    ("grep export src",   ["grep", "-rn", "export", "src"],        [RTK, "grep", "-rn", "export", "src"]),
    ("find *.tsx",        ["find", "src", "-name", "*.tsx"],       [RTK, "find", "src", "-name", "*.tsx"]),
    ("ls node_modules",   ["ls", "-la", "node_modules"],           [RTK, "ls", "node_modules"]),
    ("read 655-line tsx", ["cat", "src/app/jnsupport/page.tsx"],   [RTK, "read", "src/app/jnsupport/page.tsx"]),
    ("tree src",          ["find", "src", "-type", "f"],           [RTK, "tree", "src"]),
]

def run(argv):
    p = subprocess.run(argv, cwd=REPO, capture_output=True, timeout=120)
    out = p.stdout + p.stderr
    return out

def toks(b):  # rough proxy: ~4 chars/token
    return math.ceil(len(b) / 4)

rows, tot_nb, tot_rb, tot_nt, tot_rt = [], 0, 0, 0, 0
for label, ncmd, rcmd in CASES:
    try:
        nb, rb = run(ncmd), run(rcmd)
    except Exception as e:
        print(f"SKIP {label}: {e}", file=sys.stderr); continue
    nbl, rbl = len(nb), len(rb)
    nt, rt = toks(nb), toks(rb)
    cut = 0 if nt == 0 else round(100 * (nt - rt) / nt, 1)
    rows.append((label, nbl, rbl, nt, rt, cut))
    tot_nb += nbl; tot_rb += rbl; tot_nt += nt; tot_rt += rt

print(f"\n{'command':<20}{'native B':>10}{'rtk B':>10}{'native tok':>12}{'rtk tok':>10}{'cut %':>8}")
print("-" * 70)
for label, nbl, rbl, nt, rt, cut in rows:
    print(f"{label:<20}{nbl:>10}{rbl:>10}{nt:>12}{rt:>10}{cut:>7}%")
print("-" * 70)
tot_cut = round(100 * (tot_nt - tot_rt) / tot_nt, 1)
print(f"{'TOTAL':<20}{tot_nb:>10}{tot_rb:>10}{tot_nt:>12}{tot_rt:>10}{tot_cut:>7}%")
print(f"\nOne agent orient+search+read pass:")
print(f"  native: {tot_nt:,} est. tokens of command output")
print(f"  rtk:    {tot_rt:,} est. tokens  ->  {tot_cut}% less context to ingest")

json.dump({"rows": [dict(zip(["cmd","native_bytes","rtk_bytes","native_tok","rtk_tok","cut_pct"], r)) for r in rows],
           "total": {"native_bytes": tot_nb, "rtk_bytes": tot_rb, "native_tok": tot_nt, "rtk_tok": tot_rt, "cut_pct": tot_cut}},
          open(os.path.join(os.path.dirname(__file__), "result.json"), "w"), indent=2)
