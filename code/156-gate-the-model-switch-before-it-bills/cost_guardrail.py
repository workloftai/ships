#!/usr/bin/env python3
"""cost_guardrail.py — a PreModelSwitch hook that refuses an upgrade to a
premium model once the day's budget is gone, before a single token is billed.

Claude Code v2.1.251 added the PreModelSwitch hook event. It fires *before* the
session applies a model switch and, uniquely for a Claude Code hook, it can
block that switch (exit code 2). That is the missing lever for cost control:
until now you found out you had burned the budget on the invoice, after the
tokens were spent. This fires at the moment of the switch, before the expensive
model is ever called.

Contract (from the v2.1.251 hooks docs). stdin JSON:
    {
      "hook_event_name": "PreModelSwitch",
      "session_id": "...",
      "cwd": "...",
      "from_model": "claude-haiku-4-5",   # canonical name of current model
      "to_model":   "claude-opus-4-8"      # canonical name of model switching to
    }

We decide by tier, not by exact id, so new model names don't need a code change:
any name containing "haiku" < "sonnet"/"fable" < "opus". A downgrade or a lateral
move always passes. An *upgrade into a premium tier* is gated: if today's spend
(read from a ledger you feed) has hit the daily budget, we deny with exit 2 and a
reason the user sees. Everything else passes.

Design rule: FAIL OPEN. A cost guard that bricks the fleet on its own bug is
worse than the overspend it prevents. Any error, any unknown model, any missing
policy -> allow the switch and exit 0. The guard can only ever say "no" when it
is certain; when in doubt it gets out of the way.

Wire it in settings.json:
    {
      "hooks": {
        "PreModelSwitch": [
          { "matcher": ".*opus.*",
            "hooks": [ { "type": "command",
                         "command": "python3 /path/to/cost_guardrail.py" } ] }
        ]
      }
    }
The matcher is optional (it runs on every switch without one); scoping it to
".*opus.*" means the guard is only even invoked when something reaches for the
premium tier, which is the only case it acts on anyway.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Where to look for the policy file: env override, else next to this script.
POLICY_ENV = "COST_POLICY"
DEFAULT_POLICY_NAME = "cost_policy.json"

# Baked-in fallback so the guard still behaves sanely with no policy file at all.
# Prices are Anthropic public list prices per million tokens (input/output) as a
# rough tier ordering; edit cost_policy.json for your own gateway/contract rates.
FALLBACK_POLICY = {
    "tiers": {"haiku": 1, "fable": 2, "sonnet": 2, "opus": 3},
    "prices_per_mtok_out": {"haiku": 5, "sonnet": 15, "fable": 15, "opus": 75},
    "premium_tier": 3,
    "daily_budget": 5.00,
    "currency": "$",
    "ledger_path": "~/.claude/cost_ledger.jsonl",
    "decision_log": "~/.claude/cost_guardrail_decisions.jsonl",
    "allowlist_sessions": [],
    "allow_downgrades": True,
}


def _load_policy():
    path = os.environ.get(POLICY_ENV)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            DEFAULT_POLICY_NAME)
    try:
        with open(os.path.expanduser(path)) as fh:
            user = json.load(fh)
        merged = dict(FALLBACK_POLICY)
        merged.update(user)
        return merged
    except Exception:
        # No policy, unreadable, or malformed -> use the safe fallback.
        return dict(FALLBACK_POLICY)


def _tier_of(model_name, tiers):
    """Ordinal cost tier by substring match; 0 (unknown -> fail open) if none."""
    if not model_name:
        return 0
    name = model_name.lower()
    # Longest key first so "opus" wins over a shorter accidental match.
    for key in sorted(tiers, key=len, reverse=True):
        if key in name:
            return tiers[key]
    return 0


def _spend_today(ledger_path):
    """Sum `cost` over today's rows in a JSONL ledger. Missing/broken -> 0.0.

    You feed this ledger from wherever your spend is reported: the v2.1.251
    `rate_limits.spend_limit` status-line field, an audit log, or one appended
    line per billed action: {"ts": "<iso8601>", "cost": <float>}.
    """
    path = os.path.expanduser(ledger_path or "")
    if not path or not os.path.exists(path):
        return 0.0
    today = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                ts = str(row.get("ts", ""))
                if ts[:10] == today:
                    try:
                        total += float(row.get("cost", 0) or 0)
                    except (TypeError, ValueError):
                        continue
    except Exception:
        return 0.0
    return total


def _log_decision(policy, record):
    path = os.path.expanduser(policy.get("decision_log") or "")
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass  # never let logging failure change the decision


def _allow(reason, extra=None):
    """Emit an allow decision and exit 0. Context is best-effort on this event."""
    out = {"hookSpecificOutput": {
        "hookEventName": "PreModelSwitch",
        "permissionDecision": "allow",
        "permissionDecisionReason": reason,
    }}
    if extra:
        out["additionalContext"] = extra
    print(json.dumps(out))
    sys.exit(0)


def _deny(reason):
    """Emit a deny decision and exit 2 to hard-block the switch."""
    out = {"hookSpecificOutput": {
        "hookEventName": "PreModelSwitch",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}
    print(json.dumps(out))
    # Reason also to stderr so it surfaces even if JSON is ignored.
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def decide(event, policy):
    """Pure decision core. Returns ("allow"|"deny", reason, context). No I/O
    except the ledger read, which is itself fail-open. Kept separate so the test
    harness can drive it against the documented payload without a live switch.
    """
    tiers = policy.get("tiers", {})
    from_model = event.get("from_model", "")
    to_model = event.get("to_model", "")
    from_tier = _tier_of(from_model, tiers)
    to_tier = _tier_of(to_model, tiers)
    cur = policy.get("currency", "$")

    # Unknown target tier -> fail open.
    if to_tier == 0:
        return "allow", f"{to_model} not in policy; not gated.", None

    # Downgrade or lateral move: always fine, note the saving.
    if to_tier <= from_tier:
        return "allow", f"Switch to {to_model} is not an upgrade; allowed.", None

    # Upgrade. Only premium-tier upgrades are gated.
    premium = policy.get("premium_tier", max(tiers.values()) if tiers else 3)
    if to_tier < premium:
        return "allow", f"Upgrade to {to_model} below premium tier; allowed.", None

    # Premium upgrade. Allowlisted session bypasses the gate.
    if event.get("session_id") in set(policy.get("allowlist_sessions", [])):
        return "allow", f"Session allowlisted; premium switch to {to_model} allowed.", None

    budget = float(policy.get("daily_budget", 0) or 0)
    spent = _spend_today(policy.get("ledger_path"))
    if budget > 0 and spent >= budget:
        return ("deny",
                (f"Daily budget {cur}{budget:.2f} exhausted ({cur}{spent:.2f} spent). "
                 f"Switch {from_model} -> {to_model} blocked. Raise daily_budget, "
                 f"allowlist this session, or wait for the next day."),
                None)

    prices = policy.get("prices_per_mtok_out", {})
    fp = next((prices[k] for k in prices if k in (from_model or "").lower()), None)
    tp = next((prices[k] for k in prices if k in (to_model or "").lower()), None)
    mult = f" (~{tp / fp:.0f}x the per-token cost of {from_model})" if fp and tp and fp else ""
    ctx = (f"Premium switch to {to_model}{mult}. "
           f"{cur}{spent:.2f} of {cur}{budget:.2f} used today.")
    return "allow", f"Premium switch to {to_model} within budget; allowed.", ctx


def main():
    # Read + parse stdin. Anything wrong -> fail open.
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        _allow("Unparseable hook input; failing open.")

    policy = _load_policy()
    try:
        verdict, reason, ctx = decide(event, policy)
    except Exception as exc:  # any bug in the guard -> allow
        _allow(f"Guard error ({exc}); failing open.")

    _log_decision(policy, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": event.get("session_id"),
        "from_model": event.get("from_model"),
        "to_model": event.get("to_model"),
        "verdict": verdict,
        "reason": reason,
    })

    if verdict == "deny":
        _deny(reason)
    else:
        _allow(reason, ctx)


if __name__ == "__main__":
    main()
