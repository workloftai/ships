#!/usr/bin/env python3
"""fleet-cost — what our Claude Code usage actually costs.

Reads the session logs Claude Code already writes under ~/.claude/projects
(one JSONL per session; every assistant line carries model + token usage) and
turns them into a cost breakdown by day, model, and workspace. No third-party
tool, no telemetry, nothing leaves the box — it just adds up numbers that are
already sitting on disk.

Caveat it states honestly: this sees CLAUDE CODE usage only. Fleet agents that
call the API directly (Walt, Gary, Maggie, and the rest) bill separately and do
not write to ~/.claude/projects, so they are not counted here.

Costs are list-price estimates from the published per-MTok rates below, not a
billed invoice. Cache reads and writes are priced at their real multipliers
(read 0.1x, 5-min write 1.25x, 1-hour write 2x of base input).

Usage:
    fleet-cost                 # last 30 days, grouped by day
    fleet-cost --days 7        # last 7 days
    fleet-cost --by workspace  # group by workspace instead of day
    fleet-cost --by model      # group by model
    fleet-cost --json          # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"

# Published list prices, $/MTok (input, output). Base input rate also prices
# cache: read = 0.1x, 5-min write = 1.25x, 1-hour write = 2x.
PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
}
CACHE_READ_MULT = 0.1
CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.0


def price_line(model: str, u: dict) -> tuple[float, dict]:
    """Return (dollar cost, token dict) for one assistant usage record."""
    base_in, out_rate = PRICES.get(model, (5.0, 25.0))  # default to Opus rate
    base_in /= 1_000_000
    out_rate /= 1_000_000

    uncached_in = u.get("input_tokens", 0) or 0
    output = u.get("output_tokens", 0) or 0
    cache_read = u.get("cache_read_input_tokens", 0) or 0

    cc = u.get("cache_creation") or {}
    eph_5m = cc.get("ephemeral_5m_input_tokens")
    eph_1h = cc.get("ephemeral_1h_input_tokens")
    if eph_5m is None and eph_1h is None:
        # No breakdown — treat the whole cache-creation figure as a 5-min write.
        eph_5m = u.get("cache_creation_input_tokens", 0) or 0
        eph_1h = 0
    eph_5m = eph_5m or 0
    eph_1h = eph_1h or 0

    cost = (
        uncached_in * base_in
        + output * out_rate
        + cache_read * base_in * CACHE_READ_MULT
        + eph_5m * base_in * CACHE_WRITE_5M_MULT
        + eph_1h * base_in * CACHE_WRITE_1H_MULT
    )
    tokens = {
        "input": uncached_in,
        "output": output,
        "cache_read": cache_read,
        "cache_write": eph_5m + eph_1h,
    }
    return cost, tokens


def workspace_of(project_dir: str) -> str:
    """Turn an encoded project dir name into a readable workspace label."""
    # Claude Code encodes the cwd as a dash-joined path, e.g.
    # "-home-workloft-conexus" or "-tmp-...-scratchpad-...".
    parts = [p for p in project_dir.split("-") if p]
    if "conexus" in parts:
        return "conexus (ReferRoute)"
    if "scratchpad" in project_dir or project_dir.startswith("-tmp"):
        return "scratchpad / temp"
    # Last meaningful path segment.
    return parts[-1] if parts else project_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--by", choices=["day", "workspace", "model"], default="day")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not PROJECTS.exists():
        print(f"no Claude Code logs at {PROJECTS}", file=sys.stderr)
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    groups: dict[str, dict] = defaultdict(
        lambda: {"cost": 0.0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    )
    total = {"cost": 0.0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    models_seen: dict[str, float] = defaultdict(float)
    lines_read = 0

    for jsonl in PROJECTS.rglob("*.jsonl"):
        ws = workspace_of(jsonl.parent.name)
        try:
            with jsonl.open() as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("type") != "assistant":
                        continue
                    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
                    model = msg.get("model") or o.get("model")
                    usage = msg.get("usage") or o.get("usage")
                    ts = o.get("timestamp")
                    if not (model and usage and ts):
                        continue
                    if model == "<synthetic>":  # Claude Code's own injected turns
                        continue
                    try:
                        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    if when < cutoff:
                        continue
                    cost, tok = price_line(model, usage)
                    if args.by == "day":
                        key = when.date().isoformat()
                    elif args.by == "workspace":
                        key = ws
                    else:
                        key = model
                    g = groups[key]
                    g["cost"] += cost
                    for k in ("input", "output", "cache_read", "cache_write"):
                        g[k] += tok[k]
                    total["cost"] += cost
                    for k in ("input", "output", "cache_read", "cache_write"):
                        total[k] += tok[k]
                    models_seen[model] += cost
                    lines_read += 1
        except Exception:
            continue

    if args.json:
        print(json.dumps({"total": total, "groups": groups, "by_model": models_seen}, indent=2))
        return 0

    def fmt_tok(n: int) -> str:
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}k"
        return str(n)

    print(f"Claude Code cost, last {args.days} days  (list-price estimate, not billed)")
    print(f"Grouped by {args.by}.  {lines_read:,} assistant turns across the logs.\n")
    header = f"{args.by:<22} {'cost':>9}  {'in':>7} {'out':>7} {'cache rd':>9} {'cache wr':>9}"
    print(header)
    print("-" * len(header))
    for key in sorted(groups, key=lambda k: groups[k]["cost"], reverse=True):
        g = groups[key]
        print(
            f"{key:<22} ${g['cost']:>8.2f}  "
            f"{fmt_tok(g['input']):>7} {fmt_tok(g['output']):>7} "
            f"{fmt_tok(g['cache_read']):>9} {fmt_tok(g['cache_write']):>9}"
        )
    print("-" * len(header))
    print(
        f"{'TOTAL':<22} ${total['cost']:>8.2f}  "
        f"{fmt_tok(total['input']):>7} {fmt_tok(total['output']):>7} "
        f"{fmt_tok(total['cache_read']):>9} {fmt_tok(total['cache_write']):>9}"
    )
    tok_total = sum(total[k] for k in ("input", "output", "cache_read", "cache_write"))
    if tok_total:
        cache_tok = total["cache_read"] + total["cache_write"]
        print(
            f"\nCache was {100*cache_tok/tok_total:.0f}% of all tokens. "
            f"By model: "
            + ", ".join(
                f"{m.replace('claude-','')} ${c:.0f}"
                for m, c in sorted(models_seen.items(), key=lambda x: -x[1])
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
