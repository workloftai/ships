#!/usr/bin/env python3
"""Proof that the guard makes the right call on the real PreModelSwitch payload.

We cannot fire a live model switch from a test, so we do the next honest thing:
drive the guard with the exact stdin schema Claude Code v2.1.251 documents, and
assert both the decision core and the process-level exit codes (0 allow / 2
block). Run: python3 test_cost_guardrail.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cost_guardrail as g  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def event(frm, to, session="s1"):
    """A realistic PreModelSwitch payload per the v2.1.251 docs."""
    return {
        "hook_event_name": "PreModelSwitch",
        "session_id": session,
        "cwd": "/home/agent/proj",
        "permission_mode": "default",
        "from_model": frm,
        "to_model": to,
    }


_LEDGER_SEQ = [0]


def policy(budget=5.0, spent=0.0, allowlist=None, tmpdir=None):
    _LEDGER_SEQ[0] += 1
    ledger = os.path.join(tmpdir, f"ledger-{_LEDGER_SEQ[0]}.jsonl")
    if spent:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).isoformat()
        with open(ledger, "w") as fh:
            fh.write(json.dumps({"ts": today, "cost": spent}) + "\n")
    return {
        "tiers": {"haiku": 1, "fable": 2, "sonnet": 2, "opus": 3},
        "prices_per_mtok_out": {"haiku": 5, "sonnet": 15, "fable": 15, "opus": 75},
        "premium_tier": 3,
        "daily_budget": budget,
        "currency": "$",
        "ledger_path": ledger,
        "decision_log": os.path.join(tmpdir, "decisions.jsonl"),
        "allowlist_sessions": allowlist or [],
    }


def test_decision_core():
    print("decision core:")
    with tempfile.TemporaryDirectory() as td:
        p_ok = policy(budget=5.0, spent=0.0, tmpdir=td)
        p_broke = policy(budget=5.0, spent=9.99, tmpdir=td)

        v, _, _ = g.decide(event("claude-opus-4-8", "claude-haiku-4-5"), p_ok)
        check("downgrade opus->haiku is allowed", v == "allow")

        v, _, _ = g.decide(event("claude-sonnet-5", "claude-fable-5"), p_ok)
        check("lateral sonnet->fable (same tier) is allowed", v == "allow")

        v, _, _ = g.decide(event("claude-haiku-4-5", "claude-sonnet-5"), p_ok)
        check("upgrade to sub-premium sonnet is allowed", v == "allow")

        v, _, ctx = g.decide(event("claude-haiku-4-5", "claude-opus-4-8"), p_ok)
        check("premium upgrade under budget is allowed", v == "allow")
        check("premium upgrade under budget is annotated with a multiplier",
              ctx is not None and "x the per-token cost" in ctx)

        v, reason, _ = g.decide(event("claude-haiku-4-5", "claude-opus-4-8"), p_broke)
        check("premium upgrade over budget is DENIED", v == "deny")
        check("deny reason names the budget", "budget" in reason.lower())

        p_allow = policy(budget=5.0, spent=9.99, allowlist=["s1"], tmpdir=td)
        v, _, _ = g.decide(event("claude-haiku-4-5", "claude-opus-4-8", "s1"), p_allow)
        check("allowlisted session bypasses the gate even over budget", v == "allow")

        v, _, _ = g.decide(event("some-future-model", "another-unknown"), p_broke)
        check("unknown target model fails open (allowed)", v == "allow")


def run_proc(payload):
    """Run the hook as a real process; return (exit_code, parsed_stdout)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "cost_guardrail.py")],
        input=json.dumps(payload), capture_output=True, text=True,
        env={**os.environ, "COST_POLICY": PROC_POLICY_PATH},
    )
    try:
        out = json.loads(proc.stdout)
    except Exception:
        out = {}
    return proc.returncode, out


def test_process_exit_codes(tmpdir):
    print("process exit codes:")
    code, out = run_proc(event("claude-opus-4-8", "claude-haiku-4-5"))
    check("downgrade exits 0", code == 0)
    check("downgrade decision is allow",
          out.get("hookSpecificOutput", {}).get("permissionDecision") == "allow")

    code, out = run_proc(event("claude-haiku-4-5", "claude-opus-4-8"))
    check("over-budget premium upgrade exits 2 (blocks)", code == 2)
    check("over-budget decision is deny",
          out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")

    # Garbage stdin must fail open (exit 0), never brick the fleet.
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "cost_guardrail.py")],
        input="not json at all", capture_output=True, text=True,
        env={**os.environ, "COST_POLICY": PROC_POLICY_PATH},
    )
    check("garbage stdin fails open (exit 0)", proc.returncode == 0)


if __name__ == "__main__":
    test_decision_core()
    with tempfile.TemporaryDirectory() as td:
        # Process-level tests use an over-budget policy on disk so the premium
        # upgrade is the one that blocks.
        pol = policy(budget=5.0, spent=9.99, tmpdir=td)
        PROC_POLICY_PATH = os.path.join(td, "policy.json")
        with open(PROC_POLICY_PATH, "w") as fh:
            json.dump(pol, fh)
        test_process_exit_codes(td)

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
