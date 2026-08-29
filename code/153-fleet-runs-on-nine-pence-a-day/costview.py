#!/usr/bin/env python3
"""
costview — where the fleet's money actually goes, read from the audit log.

Every action the fleet takes is logged to workloft_audit_log with a cost. We had
50k+ cost-bearing rows and no view of them, so spend was a monthly surprise, not a
signal. This reads those rows over a window and aggregates them by agent, model,
action and actor, prints a summary, and writes a self-contained HTML dashboard.

No Grafana, no collector, no new infra: the data was already there, we just never
looked at it. (The Claude Code to OpenTelemetry to Grafana streaming version is
the phase-two build, for live dashboards; this is the read-what-you-already-have
version, and it answers the question tonight.)

Usage:
    python3 costview.py --days 30 --out dashboard.html
Dependency-free: stdlib only, reuses the audit logger's Supabase creds.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/home/workloft")
from audit import logger  # noqa: E402

PAGE = 1000


def fetch_cost_rows(since_iso):
    base, key = logger._creds()
    base = base.rstrip("/")
    hdr = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows, offset = [], 0
    sel = "agent,tool,action,actor,cost_usd,created_at"
    while True:
        url = (f"{base}/rest/v1/workloft_audit_log?select={sel}"
               f"&cost_usd=gt.0&created_at=gte.{since_iso}"
               f"&order=created_at.asc&limit={PAGE}&offset={offset}")
        req = urllib.request.Request(url, headers=hdr)
        batch = json.load(urllib.request.urlopen(req, timeout=60))
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    return rows


def _bucket(rows, key_fn):
    agg = {}
    for r in rows:
        k = key_fn(r) or "(none)"
        a = agg.setdefault(k, {"cost": 0.0, "n": 0})
        a["cost"] += float(r.get("cost_usd") or 0)
        a["n"] += 1
    return dict(sorted(agg.items(), key=lambda kv: -kv[1]["cost"]))


def aggregate(rows):
    total = sum(float(r.get("cost_usd") or 0) for r in rows)
    return {
        "total": total,
        "rows": len(rows),
        "by_agent": _bucket(rows, lambda r: r.get("agent")),
        "by_model": _bucket(rows, lambda r: r.get("tool")),
        "by_action": _bucket(rows, lambda r: r.get("action")),
        "by_actor": _bucket(rows, lambda r: r.get("actor")),
        "by_day": _bucket(rows, lambda r: str(r.get("created_at"))[:10]),
    }


def print_summary(agg, days):
    print(f"\n=== fleet spend, last {days} days ===")
    print(f"total ${agg['total']:.2f} across {agg['rows']} cost-bearing actions "
          f"(${agg['total']/max(1,days):.2f}/day)\n")
    for title, key in [("model", "by_model"), ("agent", "by_agent"),
                       ("action", "by_action")]:
        print(f"top {title}s by spend:")
        for name, v in list(agg[key].items())[:6]:
            share = 100 * v["cost"] / agg["total"] if agg["total"] else 0
            print(f"  ${v['cost']:8.2f}  {share:4.1f}%  {v['n']:6d}x  {name}")
        print()


def _bars(bucket, total, limit=8):
    out = []
    top = list(bucket.items())[:limit]
    mx = max((v["cost"] for _n, v in top), default=1) or 1
    for name, v in top:
        pct = 100 * v["cost"] / total if total else 0
        w = max(1, round(100 * v["cost"] / mx))
        out.append(
            f'<div class="row"><div class="lbl">{_esc(name)}</div>'
            f'<div class="bar"><span style="width:{w}%"></span></div>'
            f'<div class="val">${v["cost"]:.2f} <em>{pct:.0f}%</em> '
            f'<small>{v["n"]}x</small></div></div>')
    return "\n".join(out)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(agg, days, generated):
    total = agg["total"]
    css = """
    :root{--ink:#181818;--red:#FA3E33;--muted:#9a9a9a;--border:#e6e6e6;--bg:#fff;--surf:#fafafa}
    *{box-sizing:border-box;margin:0}
    body{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:#1a1a1a;background:var(--bg);padding:0 0 60px}
    .band{background:var(--ink);color:#fff;padding:22px 32px;display:flex;justify-content:space-between;align-items:baseline}
    .band h1{font-size:20px;font-weight:700;letter-spacing:-.01em}
    .band .eye{color:var(--muted);text-transform:uppercase;letter-spacing:.14em;font-size:11px}
    .rule{height:3px;background:var(--red)}
    .wrap{max-width:900px;margin:28px auto;padding:0 24px}
    .kpis{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}
    .kpi{flex:1;min-width:150px;border:1px solid var(--border);border-top:3px solid var(--red);border-radius:2mm;padding:16px 18px;background:var(--surf)}
    .kpi .n{font-size:26px;font-weight:700}
    .kpi .k{color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-size:10px;margin-top:4px}
    h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:#8a8a8a;margin:30px 0 12px;font-weight:700}
    .row{display:grid;grid-template-columns:200px 1fr 150px;gap:12px;align-items:center;padding:5px 0}
    .lbl{font-size:13px;font-family:"Courier New",monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .bar{background:#f0f0f0;border-radius:2px;height:14px;overflow:hidden}
    .bar span{display:block;height:100%;background:var(--red);opacity:.85}
    .val{font-size:13px;text-align:right;font-family:"Courier New",monospace}
    .val em{color:var(--muted);font-style:normal}.val small{color:#b0b0b0}
    .foot{color:#9a9a9a;font-size:11px;margin-top:36px;border-top:1px solid #eee;padding-top:14px}
    @media(max-width:640px){.row{grid-template-columns:110px 1fr 110px}}
    """
    def section(title, key):
        return f"<h2>{title}</h2>\n{_bars(agg[key], total)}"
    return f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workloft fleet cost view</title><style>{css}</style></head><body>
<div class="band"><h1>Workloft &middot; Fleet Cost View</h1>
<span class="eye">last {days} days &middot; from the audit log</span></div>
<div class="rule"></div>
<div class="wrap">
  <div class="kpis">
    <div class="kpi"><div class="n">${total:.2f}</div><div class="k">total spend</div></div>
    <div class="kpi"><div class="n">${total/max(1,days):.2f}</div><div class="k">per day</div></div>
    <div class="kpi"><div class="n">{agg['rows']:,}</div><div class="k">billed actions</div></div>
    <div class="kpi"><div class="n">${total/max(1,agg['rows'])*1000:.2f}</div><div class="k">per 1k actions</div></div>
  </div>
  {section("Spend by model", "by_model")}
  {section("Spend by agent", "by_agent")}
  {section("Spend by action", "by_action")}
  {section("Spend by actor", "by_actor")}
  {section("Spend by day", "by_day")}
  <div class="foot">Generated {generated} from workloft_audit_log. Costs are the
  per-action estimates written at log time. Read-only: no infra, no collector.
  The live-streaming version (Claude Code &rarr; OpenTelemetry &rarr; Grafana) is
  the phase-two build.</div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default="/home/workloft/costview/dashboard.html")
    a = ap.parse_args()
    since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    rows = fetch_cost_rows(since)
    agg = aggregate(rows)
    print_summary(agg, a.days)
    html = render_html(agg, a.days, dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    with open(a.out, "w") as f:
        f.write(html)
    print(f"dashboard -> {a.out}")


if __name__ == "__main__":
    main()
