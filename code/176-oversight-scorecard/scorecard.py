#!/usr/bin/env python3
"""
oversight_scorecard: Anthropic's agent-oversight measurements, applied to our fleet.

On 17 September 2026 Anthropic published how it oversees the ~30,000 agents on
its main internal platform: coverage (100% of actions pass a monitor before they
run), escalation (0.002% blocked, about 1 in 47,000; ~50 transcripts a week
reach a human), and how much of its compute goes to safety (~6%). This asks
the same questions of our fleet, from our own records, and prints where the
answer is "we can't measure that yet" instead of guessing.

Sources (read-only):
  * Claude Code transcripts (~/.claude/projects/**.jsonl): every tool call Bob
    or a subagent made, and every one a PreToolUse hook refused.
  * ~/.claude/settings.json: which hooks see which tools BEFORE they run.
  * An append-only audit log in Supabase (optional; set SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY and AUDIT_TABLE): what every other agent and
    cron recorded doing. Columns used: agent, action, category, success,
    cost_usd, created_at. Without it, section 1's fleet line reads 0.

Usage:
  python3 scorecard.py [--days 30] [--json out.json]

Stdlib only.
"""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import sys
from urllib import request

HOME = os.path.expanduser("~")
TRANSCRIPTS = os.path.join(HOME, ".claude", "projects")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
AUDIT_DIR = os.path.join(HOME, "audit")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "workloft_audit_log")

# What each pre-run hook actually inspects. A hook that only enforces ordering
# (e.g. "acknowledge Alfred first") sees the action but judges nothing about
# it, so it does not count as monitoring. Kept explicit so a reviewer can argue.
GATE_KIND = {
    "bash_longrun_gate": "safety",          # also runs bash_security_screen: droppers, reverse shells, rm -rf /, credential exfil
    "bash_security_screen": "safety",       # (attributed separately when it is the one that said no)
    "emdash_gate": "content",
    "emdash_outbound_gate": "content",
    "outbound_name_lint": "content",
    "telegram_settle_guard": "content",
    "artefact_gate": "process",
    # bash_longrun_gate's own refusals are about not blocking the chat, not safety

    "telegram_ack_gate": "ordering",
}
MONITORING = {"safety", "content", "process"}

# Tools that can reach outside the box. Unmonitored ones are the interesting gap.
OUTBOUND_TOOL = re.compile(r"^(WebFetch|WebSearch|mcp__(?!gortex|hindsight).*)$")

BLOCK_RX = re.compile(r"^PreToolUse:(\S+) hook error: (?:\[[^\]]*/(\w+)\.py\])?")
BLOCK_TEXT = [("ACK-FIRST", "telegram_ack_gate"), ("foreground loop", "bash_longrun_gate"),
              ("em-dash", "emdash_outbound_gate")]


def since_iso(days):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------ coverage map ---

def gate_map():
    """[(matcher_regex, gate_name)] for PreToolUse hooks in settings.json."""
    with open(SETTINGS) as f:
        s = json.load(f)
    out = []
    for h in s.get("hooks", {}).get("PreToolUse", []):
        m = h.get("matcher") or "*"
        rx = re.compile(".*" if m == "*" else f"^(?:{m})$")
        for hk in h.get("hooks", []):
            name = os.path.basename(hk.get("command", "").split()[-1]).replace(".py", "").replace(".sh", "")
            out.append((rx, name))
    return out


def gates_for(tool, gmap):
    return sorted({g for rx, g in gmap if rx.match(tool)})


# ------------------------------------------------------------ transcripts ----

def scan_transcripts(since):
    calls = collections.Counter()
    blocks = collections.Counter()           # gate -> n
    blocks_by_tool = collections.Counter()
    overrides = collections.Counter()
    sessions = set()
    for path in glob.glob(os.path.join(TRANSCRIPTS, "**", "*.jsonl"), recursive=True):
        if dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).isoformat() < since:
            continue
        with open(path, errors="replace") as f:
            for ln in f:
                if '"tool_use"' not in ln and '"tool_result"' not in ln:
                    continue
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                if (d.get("timestamp") or "") < since:
                    continue
                content = (d.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for it in content:
                    if it.get("type") == "tool_use":
                        name = it.get("name", "?")
                        calls[name] += 1
                        sessions.add(d.get("sessionId"))
                        if name == "Bash":
                            cmd = (it.get("input") or {}).get("command", "")
                            for tag in ("# sec-ok", "# bob-bg-ok"):
                                if tag in cmd:
                                    overrides[tag] += 1
                    elif it.get("type") == "tool_result" and it.get("is_error"):
                        t = it.get("content")
                        t = t if isinstance(t, str) else json.dumps(t)
                        m = BLOCK_RX.match(t)
                        if not m:
                            continue
                        gate = m.group(2) or next((g for k, g in BLOCK_TEXT if k in t[:400]), "unknown")
                        if "security screen" in t[:400]:
                            gate = "bash_security_screen"
                        blocks[gate] += 1
                        blocks_by_tool[m.group(1)] += 1
    return calls, blocks, blocks_by_tool, overrides, len(sessions)


# ------------------------------------------------------------ audit log -----

def _audit_creds():
    """SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from the env, else our logger's."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return url, key
    try:
        sys.path.insert(0, AUDIT_DIR)
        import logger  # noqa: E402
        return logger._creds()
    except Exception:
        return None, None


def fetch_audit(since):
    """Rows from an append-only audit table, or None if there is no audit log to read."""
    url, key = _audit_creds()
    if not (url and key):
        return None
    rows, off = [], 0
    while True:
        req = request.Request(
            f"{url}/rest/v1/{AUDIT_TABLE}?select=agent,action,category,success,cost_usd"
            f"&created_at=gte.{since}Z&order=created_at",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Range": f"{off}-{off + 999}"})
        with request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read())
        rows += page
        off += 1000
        if len(page) < 1000:
            return rows


# ------------------------------------------------------------ report --------

def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main():
    ap = argparse.ArgumentParser(prog="oversight_scorecard")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    since = since_iso(a.days)

    gmap = gate_map()
    calls, blocks, blocks_by_tool, overrides, n_sessions = scan_transcripts(since)
    total = sum(calls.values())

    per_tool = {}
    for tool, n in calls.items():
        gates = gates_for(tool, gmap)
        kinds = sorted({GATE_KIND.get(g, "unknown") for g in gates})
        per_tool[tool] = {"calls": n, "gates": gates, "monitored": any(k in MONITORING for k in kinds),
                          "safety": "safety" in kinds}
    monitored = sum(v["calls"] for v in per_tool.values() if v["monitored"])
    any_hook = sum(v["calls"] for v in per_tool.values() if v["gates"])
    safety = sum(v["calls"] for v in per_tool.values() if v["safety"])
    n_blocks = sum(blocks.values())
    unmon_out = sorted(((v["calls"], t) for t, v in per_tool.items()
                        if not v["monitored"] and OUTBOUND_TOOL.match(t)), reverse=True)
    unmon_all = sorted(((v["calls"], t) for t, v in per_tool.items() if not v["monitored"]), reverse=True)

    audit = fetch_audit(since) or []
    other = [r for r in audit if not (r["agent"] == "bob" and r["action"] in
                                      ("task_started", "task_ended", "skill_invoked"))]
    by_agent_action = collections.Counter((r["agent"], r["action"]) for r in other)
    cost = collections.defaultdict(float)
    for r in audit:
        cost[r["agent"]] += float(r["cost_usd"] or 0)

    weeks = a.days / 7
    R = {
        "window_days": a.days, "since": since,
        "bob": {"tool_calls": total, "sessions": n_sessions,
                "passed_any_prerun_hook": any_hook, "monitored_before_run": monitored,
                "safety_screened_before_run": safety, "blocked": n_blocks,
                "blocks_by_gate": dict(blocks), "blocks_by_tool": dict(blocks_by_tool),
                "overrides": dict(overrides), "unmonitored_outbound": unmon_out,
                "unmonitored_top": unmon_all[:10], "per_tool": per_tool},
        "fleet_logged_actions": len(other),
        "fleet_top_actions": by_agent_action.most_common(8),
        "recorded_cost_usd": {k: round(v, 2) for k, v in cost.items()},
    }

    print(f"OVERSIGHT SCORECARD · last {a.days} days · since {since}Z\n")
    print("1. COVERAGE: what is checked before it runs?")
    print(f"   Bob + subagents: {total:,} tool calls in {n_sessions:,} sessions")
    print(f"   passed at least one pre-run hook   {any_hook:>7,}  {pct(any_hook, total)}")
    print(f"   inspected by a hook that judges it {monitored:>7,}  {pct(monitored, total)}")
    print(f"   screened for safety (shell only)   {safety:>7,}  {pct(safety, total)}")
    print("   biggest unjudged tools:", ", ".join(f"{t} {n:,}" for n, t in unmon_all[:6]))
    print("   unjudged tools that reach outside:", ", ".join(f"{t} {n:,}" for n, t in unmon_out[:6]) or "none")
    print(f"   everything else in the fleet: {len(other):,} logged actions, screened before running: 0")
    for (ag, ac), n in by_agent_action.most_common(4):
        print(f"      {ag}/{ac}: {n:,}")
    print("\n2. ESCALATION: how often does a check say no?")
    print(f"   blocked before running: {n_blocks:,} of {total:,} = {pct(n_blocks, total)}"
          f" (1 in {total // n_blocks:,})" if n_blocks else "   blocked before running: 0")
    for g, n in blocks.most_common():
        kind = "process" if g == "bash_longrun_gate" else GATE_KIND.get(g, "?")
        print(f"      {g} [{kind}]: {n:,}")
    print(f"   overrides typed to get past a gate: {dict(overrides) or 'none'}")
    print(f"   per week: {n_blocks / weeks:.0f} blocks, each seen by the agent that tripped it, not by a human")
    print("\n3. SPEND ON CHECKING")
    print(f"   recorded model spend in the audit log: ${sum(cost.values()):.2f}"
          f" ({', '.join(f'{k} ${v:.2f}' for k, v in sorted(cost.items(), key=lambda x: -x[1]) if v)})")
    print("   checking share: NOT MEASURABLE. Our checkers (hooks, judges, the audit gate) do not")
    print("   record spend, and most of Bob's model use is on a subscription the log does not price.")

    if a.json:
        with open(a.json, "w") as f:
            json.dump(R, f, indent=1, default=list)
    return 0


if __name__ == "__main__":
    sys.exit(main())
