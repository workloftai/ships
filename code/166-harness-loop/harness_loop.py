#!/usr/bin/env python3
"""
harness-loop: read an agent's own failure log, find the instruction most tied to
the failures, and propose a rewrite grounded in the failing traces, not just the
scores. It never edits a live instruction. It writes a gated proposal for a human
to accept.

The design choice that matters: the loop can read your instructions but only
write to the proposals directory. An instruction the agent could silently rewrite
is not an instruction, it is a suggestion. So the third step of a self-improving
loop is a human, on purpose.

One stdlib file. The rewrite step calls Claude if ANTHROPIC_API_KEY is set;
without a key it still localises the culprit and writes a proposal skeleton from
the failure patterns, so the loop always runs.

Usage:
    python3 harness_loop.py --log failures.jsonl \
        --instructions instructions/ --out proposals/

Log format: one JSON object per line, e.g.
    {"instruction": "extract-postcode", "input": "...", "expected": "SW1A 1AA",
     "got": "sw1a1aa", "passed": false}
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.error
from collections import defaultdict

MODEL = "claude-opus-4-8"  # the proposer reasons over failing traces; use the strong model


# ---------------------------------------------------------------- read the log

def read_log(path):
    rows = []
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"skipping malformed line {n}: {e}", file=sys.stderr)
    return rows


# ------------------------------------------------------------ localise culprit

def localise(rows, min_runs=5):
    """Rank instructions by how much of the failure is concentrated on them.

    Returns a list of dicts sorted worst-first. An instruction is only a
    candidate culprit if it ran at least `min_runs` times, so a single unlucky
    call can't top the ranking.
    """
    runs = defaultdict(int)
    fails = defaultdict(int)
    for r in rows:
        ins = r.get("instruction", "unknown")
        runs[ins] += 1
        if not r.get("passed", False):
            fails[ins] += 1
    ranked = []
    for ins in runs:
        ranked.append({
            "instruction": ins,
            "runs": runs[ins],
            "failures": fails[ins],
            "fail_rate": round(fails[ins] / runs[ins], 3),
            "eligible": runs[ins] >= min_runs,
        })
    # worst first: eligible ones by failure count, then fail rate
    ranked.sort(key=lambda d: (d["eligible"], d["failures"], d["fail_rate"]), reverse=True)
    return ranked


def failing_traces(rows, instruction, limit=12):
    out = []
    for r in rows:
        if r.get("instruction") == instruction and not r.get("passed", False):
            out.append({
                "input": r.get("input", ""),
                "expected": r.get("expected", ""),
                "got": r.get("got", ""),
            })
            if len(out) >= limit:
                break
    return out


# ------------------------------------------------------------- propose the fix

def _call_claude(current_text, traces):
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    shown = "\n".join(
        f"  input:    {t['input']!r}\n  expected: {t['expected']!r}\n  got:      {t['got']!r}"
        for t in traces
    )
    prompt = (
        "You maintain the instruction an AI agent follows for one task. The "
        "instruction below is producing wrong answers. You are shown the actual "
        "failing traces (input, expected, what the agent produced), not just a "
        "score.\n\n"
        f"CURRENT INSTRUCTION:\n{current_text}\n\n"
        f"FAILING TRACES:\n{shown}\n\n"
        "Rewrite the instruction so these failures stop, without breaking cases "
        "that already pass. Change only what the traces justify. Reply with a "
        "single JSON object and nothing else:\n"
        '{"revised_instruction": "...", "rationale": "one or two sentences on '
        'what pattern in the traces you fixed"}'
    )
    body = json.dumps({
        "model": MODEL, "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        print(f"proposer API error: {e.code} {e.read()[:200]!r}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"proposer call failed: {e!r}", file=sys.stderr)
        return None
    text = "".join(b.get("text", "") for b in resp.get("content", []))
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"revised_instruction": text, "rationale": "model returned non-JSON; raw text kept"}


def propose(current_text, traces):
    """Return {revised_instruction, rationale, source}. Falls back to a
    deterministic skeleton when no model is available, so the loop never stalls.
    """
    llm = _call_claude(current_text, traces)
    if llm:
        llm["source"] = f"claude:{MODEL}"
        return llm
    # deterministic fallback: surface the patterns a human can act on
    diffs = [f"- input {t['input']!r} wanted {t['expected']!r} but got {t['got']!r}"
             for t in traces]
    return {
        "revised_instruction": current_text + "\n\n[PROPOSED ADDITION: address the "
        "failing cases below; no model was available to draft the rewrite.]",
        "rationale": "No ANTHROPIC_API_KEY set. Culprit localised and traces "
        "attached for a human to draft the fix from:\n" + "\n".join(diffs),
        "source": "deterministic-fallback",
    }


# ------------------------------------------------------ regression guard (v2)

def passing_cases(rows, instruction):
    """The cases this instruction already got right. These are what a rewrite
    must not break."""
    out = []
    for r in rows:
        if r.get("instruction") == instruction and r.get("passed", False):
            out.append({"input": r.get("input", ""), "expected": r.get("expected", "")})
    return out


def verify_rewrite(proposed_instruction, passing, executor):
    """Re-run the proposed instruction against every case that already passed.
    Return the list of regressions: cases the rewrite would now get wrong.

    `executor(instruction, input) -> output` is yours to supply. It is the same
    thing that produced the log in the first place, so verification runs the real
    system, not a simulation of it. An empty list means the rewrite is safe.
    """
    regressions = []
    for c in passing:
        got = " ".join(executor(proposed_instruction, c["input"]).split())
        if got != c["expected"]:
            regressions.append({**c, "got": got})
    return regressions


# ------------------------------------------------------------------- the gate

def write_proposal(out_dir, instruction, current_text, proposal, evidence,
                   regressions=None):
    """Write a gated proposal. The ONLY place this tool writes. It refuses any
    path outside out_dir, so the loop cannot reach a live instruction file.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_dir_real = os.path.realpath(out_dir)
    path = os.path.join(out_dir, f"{instruction}.proposal.md")
    if os.path.commonpath([out_dir_real, os.path.realpath(path)]) != out_dir_real:
        raise ValueError(f"refusing to write outside {out_dir}: {path}")
    if regressions is None:
        verdict = "PROPOSAL ONLY (regression check not run: no executor supplied)"
    elif regressions:
        verdict = f"NEEDS REVISION: breaks {len(regressions)} case(s) that already passed"
    else:
        verdict = "SAFE: no case that already passed regressed"
    lines = [
        f"# Proposed rewrite: {instruction}",
        "",
        "PROPOSAL ONLY. Not applied. A human must accept this before it reaches "
        "the live instruction.",
        "",
        f"Verdict: {verdict}",
        f"Source: {proposal['source']}",
        "",
        "## Rationale",
        proposal["rationale"],
        "",
        "## Current instruction",
        "```",
        current_text,
        "```",
        "",
        "## Proposed instruction",
        "```",
        proposal["revised_instruction"],
        "```",
        "",
        "## Evidence (failing traces)",
    ]
    for t in evidence:
        lines.append(f"- input {t['input']!r} → expected {t['expected']!r}, got {t['got']!r}")
    if regressions is not None:
        lines += ["", "## Regression check (cases that already passed)"]
        if regressions:
            lines.append(f"REFUSED to bless. {len(regressions)} previously-passing "
                         "case(s) would break under this rewrite:")
            for r in regressions:
                lines.append(f"- input {r['input']!r} → still expected {r['expected']!r}, "
                             f"but rewrite gives {r['got']!r}")
        else:
            lines.append("Passed. Every case that already worked still works "
                         "under this rewrite.")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def load_instruction(instr_dir, instruction):
    path = os.path.join(instr_dir, f"{instruction}.txt")
    if os.path.exists(path):
        return open(path).read().strip()
    return f"(no instruction file found at {path})"


# ------------------------------------------------------------------------ main

def run(log_path, instr_dir, out_dir, min_runs=5):
    rows = read_log(log_path)
    if not rows:
        print("empty log, nothing to do")
        return None
    ranked = localise(rows, min_runs=min_runs)
    print(f"read {len(rows)} runs across {len(ranked)} instructions\n")
    print(f"{'instruction':24} {'runs':>5} {'fails':>6} {'rate':>6}")
    for d in ranked:
        flag = "" if d["eligible"] else "  (too few runs)"
        print(f"{d['instruction']:24} {d['runs']:>5} {d['failures']:>6} {d['fail_rate']:>6}{flag}")
    culprit = next((d for d in ranked if d["eligible"] and d["failures"] > 0), None)
    if not culprit:
        print("\nno eligible instruction with failures. nothing to propose.")
        return None
    ins = culprit["instruction"]
    print(f"\nculprit: {ins} ({culprit['failures']}/{culprit['runs']} failing)")
    current = load_instruction(instr_dir, ins)
    traces = failing_traces(rows, ins)
    proposal = propose(current, traces)
    path = write_proposal(out_dir, ins, current, proposal, traces)
    print(f"wrote gated proposal: {path}")
    print("PROPOSAL ONLY. The loop did not touch any live instruction.")
    return path


def main():
    ap = argparse.ArgumentParser(description="Propose an instruction rewrite from an agent's own failure log.")
    ap.add_argument("--log", required=True, help="JSONL failure log")
    ap.add_argument("--instructions", default="instructions", help="dir of <instruction>.txt files")
    ap.add_argument("--out", default="proposals", help="dir to write gated proposals into")
    ap.add_argument("--min-runs", type=int, default=5, help="min runs before an instruction can be the culprit")
    args = ap.parse_args()
    run(args.log, args.instructions, args.out, min_runs=args.min_runs)


if __name__ == "__main__":
    main()
