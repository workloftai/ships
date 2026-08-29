#!/usr/bin/env python3
"""
distill — turn a pile of eval failures into a short list of root-cause fixes.

The self-improvement loop everyone draws has a step labelled "learn from the
failure". This is that step, made real and unglamorous. Our nightly eval writes
a KILL verdict with a rationale every time an agent's output falls below bar. We
have hundreds of them, and left alone they just accumulate as separate flags,
the same problem re-reported night after night. This reads them, clusters them by
who failed and how, and asks a model to distil each cluster into one candidate
root-cause fix, and to say whether the fault is the agent's, the rubric's, or the
logger's.

The point is not automation for its own sake. It is to collapse N scattered
failures into a handful of things worth actually fixing, and to surface the
uncomfortable share of "failures" that are the eval's own fault, not the agent's.

Usage:  python3 distill.py [--min-cluster 4] [--out distilled.json]
Reads vera/scores/vera_scores.jsonl. Dependency-free (reuses the poll router).
"""

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, "/home/workloft")
from vera import poll  # noqa: E402
ruby = poll.ruby

SCORES = os.path.join(os.path.dirname(__file__), "scores", "vera_scores.jsonl")
DISTILL_MODEL = "gpt-5-5"   # a strong reviewer; falls back handled per-call

SYS = (
    "You are a staff engineer triaging eval failures for an AI agent fleet. "
    "You are given several failure rationales, all from the SAME agent action. "
    "Find the ONE recurring root cause (ignore one-offs). Decide whose fault it "
    "is: 'agent' (the agent's output/prompt is genuinely wrong), 'rubric' (the "
    "grading criteria are stale or wrong, so good work is failed), or 'logging' "
    "(the logged record is truncated/preview-only, so the grader judged an "
    "artifact). Then write ONE concrete, testable fix.\n"
    "Return STRICT JSON only: {\"root_cause\": \"...\", \"fault\": "
    "\"agent|rubric|logging\", \"fix\": \"one concrete action\"}."
)


def load_kills():
    rows = [json.loads(l) for l in open(SCORES) if l.strip()]
    kills = defaultdict(list)
    for r in rows:
        if r.get("verdict") == "KILL":
            note = (r.get("note") or "").strip()
            if note:
                kills[(r["agent"], r["action"])].append(note)
    return kills


def distill_cluster(agent, action, notes):
    sample = notes[:12]
    user = (f"Agent action: {agent}/{action}\n"
            f"{len(notes)} failures. Rationales:\n"
            + "\n".join(f"- {n[:240]}" for n in sample))
    by = ruby._models_by_id()
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": user}]
    # Try the strong reviewer, fall back to a reliable cheap model on any error
    # or unparseable reply (gpt-5-5 over openrouter occasionally returns empty).
    for mid in (DISTILL_MODEL, "gemini-2-5-flash", "gemini-2-5-pro"):
        model = by.get(mid)
        if not model:
            continue
        try:
            raw = ruby._direct_chat(model, msgs, max_tokens=600, temperature=0.0)
            p = json.loads(poll._strip_to_json(raw))
            f = str(p.get("fault", "?")).lower().strip()
            if p.get("fix"):
                return {"root_cause": p.get("root_cause", ""), "fault": f,
                        "fix": p.get("fix", ""), "by": mid}
        except Exception:
            continue
    return {"root_cause": "(distill failed on all models)", "fault": "?",
            "fix": "", "by": "none"}


def run(min_cluster, out_path):
    kills = load_kills()
    total = sum(len(v) for v in kills.values())
    clusters = sorted(kills.items(), key=lambda kv: -len(kv[1]))
    results = []
    print(f"[distill] {total} KILL verdicts across {len(kills)} agent-actions; "
          f"distilling clusters with >= {min_cluster} failures", file=sys.stderr)
    for (agent, action), notes in clusters:
        if len(notes) < min_cluster:
            continue
        d = distill_cluster(agent, action, notes)
        d.update({"agent": agent, "action": action, "count": len(notes)})
        results.append(d)
        print(f"  {len(notes):3d}x {agent}/{action}  [{d['fault']}]  "
              f"{d['fix'][:70]}", file=sys.stderr)

    by_fault = defaultdict(int)
    for d in results:
        by_fault[d["fault"]] += d["count"]
    summary = {
        "total_kills": total,
        "clusters_distilled": len(results),
        "kills_covered": sum(d["count"] for d in results),
        "by_fault": dict(by_fault),
    }
    out = {"summary": summary, "fixes": results}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== distilled fixes (most failures first) ===")
    for d in sorted(results, key=lambda x: -x["count"]):
        print(f"\n[{d['fault'].upper()}] {d['agent']}/{d['action']} "
              f"({d['count']} failures)")
        print(f"  cause: {d['root_cause']}")
        print(f"  fix:   {d['fix']}")
    print(f"\nfault split (by failures covered): {dict(by_fault)}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-cluster", type=int, default=4)
    ap.add_argument("--out", default="/home/workloft/vera/distilled.json")
    a = ap.parse_args()
    run(a.min_cluster, a.out)
