#!/usr/bin/env python3
"""spend_guard — a tripwire on an agent fleet's model spend.

If your agents route to the cheapest capable model and log every call's cost,
you have the *data* to catch a runaway. What you usually don't have is anything
that WATCHES that data. So the runaway loop, the credit drain, the day one agent
starts leaning on the premium tier — you find out when the bill arrives.

This is the missing watcher. It reads your per-call cost log, compares the last
24h against a trailing baseline, and shouts only when a rule trips. It alerts,
it does not enforce: hard-capping a call mid-flight is a separate, riskier step.
Eyes first.

The rule engine (`analyse`) is pure — hand it a list of log rows and it returns
the verdict. `demo.py` and the tests run it entirely offline. Wiring it to your
own store (Supabase, a warehouse, a JSONL file) is one function, `fetch_rows`.

Each row is a dict:
    {"created_at": ISO8601, "agent": str, "action": str,
     "cost_usd": float, "arguments": {"tier": str, "category": str}}

Rules (trailing 24h vs prior N days):
  1. Fleet spend spike  — today > max(FLEET_FLOOR, median * SPIKE_MULT)
  2. Agent spend spike   — same, per agent
  3. Premium-tier spend  — the expensive escalation rung; a day that leans on it
                           is surfaced (whether it is misuse is your call)
  4. Failover storm      — retries today >> baseline (a provider is down/blocked)

Alerting and the store are yours; the discipline that matters is: silent when
clean, one message when not.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Config:
    fleet_floor: float = 1.00      # $/day below which a fleet spike is noise
    agent_floor: float = 0.50      # $/day, per agent
    premium_floor: float = 0.25    # $/day of premium-tier spend worth surfacing
    spike_mult: float = 3.0        # today must exceed baseline median by this
    failover_floor: int = 40       # retries/day below which a storm is noise
    baseline_days: int = 7
    failover_action: str = "chat_failover"   # the row action that marks a retry
    # Categories where the premium tier is never expected — routine, cheaply
    # served work. Premium spend here earns an extra flag.
    cheap_eligible: set = field(default_factory=lambda: {
        "classify", "extract", "copy", "chat_cheap"})


def _window_index(created_at: str, now: datetime, baseline_days: int) -> int | None:
    """Which trailing-24h window a row falls in. 0 = last 24h, 1..N = prior days."""
    try:
        ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = (now - ts).total_seconds() / 86400.0
    if age_days < 0:
        return 0
    idx = int(age_days)
    return idx if idx <= baseline_days else None


def _median(vals: list[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def analyse(rows: list[dict], now: datetime | None = None,
            cfg: Config | None = None) -> dict:
    """Pure rule engine. Bucket rows into 24h windows, evaluate the four rules,
    return {findings, today, fleet_base, n_rows}."""
    now = now or datetime.now(timezone.utc)
    cfg = cfg or Config()
    N = cfg.baseline_days

    buckets: dict[int, dict] = {
        w: {"fleet": 0.0, "agents": {}, "premium": 0.0,
            "premium_by_cat": {}, "failover": 0}
        for w in range(N + 1)
    }
    for r in rows:
        w = _window_index(r.get("created_at", ""), now, N)
        if w is None:
            continue
        b = buckets[w]
        cost = float(r.get("cost_usd") or 0)
        agent = r.get("agent") or "external"
        b["fleet"] += cost
        b["agents"][agent] = b["agents"].get(agent, 0.0) + cost
        if r.get("action") == cfg.failover_action:
            b["failover"] += 1
        args = r.get("arguments") or {}
        if isinstance(args, dict) and args.get("tier") == "premium":
            b["premium"] += cost
            cat = args.get("category") or "(uncat)"
            slot = b["premium_by_cat"].setdefault(cat, [0.0, 0])
            slot[0] += cost
            slot[1] += 1

    today = buckets[0]
    prior = [buckets[w] for w in range(1, N + 1)]
    findings: list[str] = []

    # Rule 1 — fleet spend spike
    fleet_base = _median([b["fleet"] for b in prior])
    fleet_trip = max(cfg.fleet_floor, fleet_base * cfg.spike_mult)
    if today["fleet"] > fleet_trip:
        findings.append(
            f"Fleet spend ${today['fleet']:.2f} today vs ${fleet_base:.2f} "
            f"median (x{cfg.spike_mult:g} = ${fleet_trip:.2f} trip)")

    # Rule 2 — per-agent spend spike
    agents = set(today["agents"])
    for b in prior:
        agents |= set(b["agents"])
    for a in sorted(agents):
        a_today = today["agents"].get(a, 0.0)
        a_base = _median([b["agents"].get(a, 0.0) for b in prior])
        a_trip = max(cfg.agent_floor, a_base * cfg.spike_mult)
        if a_today > a_trip:
            findings.append(
                f"Agent '{a}' spend ${a_today:.2f} today vs ${a_base:.2f} "
                f"median (trip ${a_trip:.2f})")

    # Rule 3 — premium-tier spend
    if today["premium"] > cfg.premium_floor:
        cats = sorted(today["premium_by_cat"].items(), key=lambda kv: -kv[1][0])
        detail = ", ".join(f"{c} (${v[0]:.2f}/{v[1]}x)" for c, v in cats[:4])
        cheap_misuse = [c for c, _ in cats if c in cfg.cheap_eligible]
        line = f"Premium tier ${today['premium']:.2f} today across: {detail}"
        if cheap_misuse:
            line += f"  premium on cheap-eligible: {', '.join(cheap_misuse)}"
        findings.append(line)

    # Rule 4 — failover storm
    fo_base = _median([b["failover"] for b in prior])
    fo_trip = max(cfg.failover_floor, fo_base * cfg.spike_mult)
    if today["failover"] > fo_trip:
        findings.append(
            f"Failover storm: {today['failover']} retries today vs "
            f"{fo_base:.0f} median (trip {fo_trip:.0f}) — a provider may be "
            f"down/blocked and the router is burning retries")

    return {"findings": findings, "today": today,
            "fleet_base": fleet_base, "n_rows": len(rows)}


# ── wiring: replace fetch_rows and alert for your own store / channel ──────────

def fetch_rows(now: datetime, cfg: Config) -> list[dict]:
    """Page your per-call cost log for the window. This reference reads a
    Supabase/PostgREST table; swap it for a warehouse query or a JSONL read.
    Reads creds from the env — no secrets in source."""
    import json
    import urllib.parse
    import urllib.request

    base = os.environ.get("AUDIT_DB_URL", "").rstrip("/")
    key = os.environ.get("AUDIT_DB_KEY", "")
    table = os.environ.get("AUDIT_DB_TABLE", "audit_log")
    if not base or not key:
        raise RuntimeError("set AUDIT_DB_URL and AUDIT_DB_KEY to fetch live rows")
    since = (now - timedelta(days=cfg.baseline_days + 1)).isoformat()
    since_q = urllib.parse.quote(since)
    rows: list[dict] = []
    page, offset = 1000, 0
    while True:
        url = (f"{base}/rest/v1/{table}?select=agent,action,cost_usd,arguments,created_at"
               f"&created_at=gte.{since_q}&order=created_at.asc&limit={page}&offset={offset}")
        req = urllib.request.Request(
            url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def alert(text: str) -> None:
    """Where a trip goes. This reference posts to Telegram if configured, else
    prints. Swap for Slack, PagerDuty, email — your channel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        import urllib.parse
        import urllib.request
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()),
            timeout=15)
    else:
        print(text)


def main() -> int:
    import sys
    cfg = Config()
    now = datetime.now(timezone.utc)
    rows = fetch_rows(now, cfg)
    v = analyse(rows, now, cfg)
    if not v["findings"]:
        return 0  # silent when clean
    alert("Spend guardrail tripped:\n" + "\n".join("- " + f for f in v["findings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
