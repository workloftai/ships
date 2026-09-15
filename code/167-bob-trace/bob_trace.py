#!/usr/bin/env python3
"""
bob-trace  —  turn every detached background job into an inspectable trace.

WHY THIS EXISTS
  Interactive agent sessions are already traced: Claude Code hooks emit spans
  to Phoenix, Grafana/VictoriaMetrics carry the metrics, Langfuse holds the
  LLM deep-dives. But bob-bg jobs run DETACHED, outside the agent process tree
  (that is the whole point of bob-bg — it dodges the runaway-turn watchdog).
  So they fire no hooks and appear in none of that. Every background job has
  only a thin status+rc record and a raw log. When one fails you get "failed
  rc=-15" and a wall of text. That is the blind spot this closes.

WHAT IT DOES
  Reads the job record (~/bob-bg/jobs/<id>.json) and its log, then derives an
  inspectable trace WITHOUT touching bob-bg itself:
    - lifecycle:  duration, timeout headroom, heartbeat stalls, terminated?
    - health:     pass/fail/timed-out/stalled/terminated verdict + reason
    - log mining: error lines, retry / rate-limit / backoff markers,
                  model calls, tokens and cost (when the log emits them)
  Then it can:
    - print the trace to the terminal          (bob-trace show <id>)
    - list recent jobs with health at a glance  (bob-trace list)
    - render a self-contained HTML trace card    (bob-trace html <id>)
    - pipe the job into the SAME Phoenix pane     (bob-trace emit <id|--all>)
      as everything else, by appending a span to the existing shipper spool.

  Dependency-free (stdlib only). Works retroactively on every job on disk.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import html as _html
import json
import os
import re
import sys
from datetime import datetime, timezone

JOBS_DIR = os.environ.get("BOBBG_JOBS", "/home/workloft/bob-bg/jobs")
SPOOL = os.environ.get(
    "BOBTRACE_SPOOL",
    "/home/workloft/observability/agent-traces/spool/spans.jsonl",
)
STALE_SECS = 180  # bob-bg reaps a running job whose heartbeat is older than this

# ----------------------------------------------------------------------------
# log-mining patterns — deliberately conservative; a false miss beats a lie
# ----------------------------------------------------------------------------
RE_ERROR = re.compile(
    r"\b(error|traceback|exception|fatal|panic|segfault)\b|\b\w+(Error|Exception)\b",
    re.I,
)
RE_FAILED = re.compile(r"\b(fail(ed|ure)?)\b", re.I)
RE_RETRY = re.compile(r"\b(retry|retrying|re-?attempt|attempt\s+\d+|backoff|rate.?limit(ed)?|throttl)\b", re.I)
RE_HTTP_ERR = re.compile(r"(?<!\d)(429|5\d\d)(?!\d)")
RE_TOKENS = re.compile(r"([\d][\d,]*)\s*tokens?\b|tokens?\s*[:=]\s*([\d][\d,]*)", re.I)
RE_COST = re.compile(r"(?:cost|spend|usd)\s*[:=]?\s*\$?\s*([\d]+\.[\d]+)|\$\s*([\d]+\.[\d]+)", re.I)
RE_MODEL = re.compile(
    r"\b(claude[-\w.]*|gpt[-\w.]*|o[134][-\w.]*|deepseek[-\w.]*|qwen[-\w.]*|"
    r"glm[-\w.]*|gemini[-\w.]*|llama[-\w.]*|mistral[-\w.]*|kimi[-\w.]*)\b",
    re.I,
)


def _now_ns() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)


def _iso_to_ns(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso).timestamp() * 1_000_000_000)
    except Exception:
        return None


def _iso_to_epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return None


def _fmt_dur(secs: float | None) -> str:
    if secs is None:
        return "-"
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def _trace_id(job_id: str) -> str:
    return hashlib.sha256(f"bobbg:{job_id}".encode()).hexdigest()[:32]


def _span_id(job_id: str, key: str) -> str:
    return hashlib.sha256(f"bobbg:{job_id}:{key}".encode()).hexdigest()[:16]


def _num(s: str) -> int:
    return int(s.replace(",", ""))


# ----------------------------------------------------------------------------
# core: build a trace record from a job's JSON + log
# ----------------------------------------------------------------------------
def load_job(job_id: str) -> dict:
    path = os.path.join(JOBS_DIR, job_id + ".json")
    with open(path) as f:
        return json.load(f)


def _read_log(job_id: str) -> list[str]:
    path = os.path.join(JOBS_DIR, job_id + ".log")
    try:
        with open(path, errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def mine_log(lines: list[str]) -> dict:
    """Extract structured signals from a raw job log. Conservative on purpose."""
    errors, retries, http_errs, models = [], 0, 0, set()
    tokens_total, cost_total = 0, 0.0
    saw_tokens = saw_cost = False
    for ln in lines:
        if RE_ERROR.search(ln) or (RE_FAILED.search(ln) and "0 failed" not in ln.lower()):
            errors.append(ln.strip()[:300])
        if RE_RETRY.search(ln):
            retries += 1
        http_errs += len(RE_HTTP_ERR.findall(ln))
        for m in RE_MODEL.findall(ln):
            models.add(m[0] if isinstance(m, tuple) else m)
        for m in RE_TOKENS.finditer(ln):
            g = m.group(1) or m.group(2)
            if g:
                saw_tokens = True
                tokens_total += _num(g)
        for m in RE_COST.finditer(ln):
            g = m.group(1) or m.group(2)
            if g:
                saw_cost = True
                cost_total += float(g)
    return {
        "log_lines": len(lines),
        "error_lines": errors[:20],
        "error_count": len(errors),
        "retries": retries,
        "http_errors": http_errs,
        "models": sorted(models),
        "tokens": tokens_total if saw_tokens else None,
        "cost_usd": round(cost_total, 4) if saw_cost else None,
    }


def build_trace(job_id: str) -> dict:
    job = load_job(job_id)
    lines = _read_log(job_id)
    mined = mine_log(lines)

    started = _iso_to_epoch(job.get("started"))
    ended = _iso_to_epoch(job.get("ended"))
    hb = _iso_to_epoch(job.get("last_heartbeat"))
    duration = (ended - started) if (started and ended) else None
    timeout = job.get("timeout") or 0
    rc = job.get("rc")
    status = job.get("status", "unknown")

    # heartbeat stall: gap between last heartbeat and the end of the job
    stall = None
    if hb and ended and (ended - hb) > STALE_SECS:
        stall = round(ended - hb)

    timed_out = bool(timeout and duration and duration >= timeout - 2)
    terminated = rc in (-15, 143)  # SIGTERM (bob-bg kill / timeout / manual stop)

    # verdict: single honest health call
    if status == "running":
        verdict, reason = "running", "job still in flight"
    elif timed_out:
        verdict, reason = "timed-out", f"hit the {_fmt_dur(timeout)} ceiling"
    elif status == "failed" and terminated:
        verdict, reason = "terminated", "killed by SIGTERM (timeout, watchdog or manual stop)"
    elif status == "failed":
        verdict, reason = "failed", f"exited rc={rc}"
    elif mined["error_count"] and status == "done":
        verdict, reason = "done-with-errors", f"{mined['error_count']} error line(s) in log despite clean exit"
    elif status == "done":
        verdict, reason = "ok", "clean exit"
    else:
        verdict, reason = status, f"rc={rc}"

    if stall and verdict not in ("ok", "running"):
        reason += f"; heartbeat stalled {_fmt_dur(stall)} before end"

    return {
        "id": job.get("id", job_id),
        "label": job.get("label", ""),
        "cmd": job.get("cmd", ""),
        "status": status,
        "verdict": verdict,
        "reason": reason,
        "rc": rc,
        "duration_s": round(duration) if duration is not None else None,
        "timeout_s": timeout or None,
        "timed_out": timed_out,
        "terminated": terminated,
        "stall_s": stall,
        "created": job.get("created"),
        "started": job.get("started"),
        "ended": job.get("ended"),
        "start_ns": _iso_to_ns(job.get("started")) or _iso_to_ns(job.get("created")),
        "end_ns": _iso_to_ns(job.get("ended")),
        **mined,
    }


# verdict -> (glyph, ansi colour)
_VERDICT_STYLE = {
    "ok": ("OK ", "\033[32m"),
    "done-with-errors": ("WARN", "\033[33m"),
    "running": ("RUN", "\033[36m"),
    "failed": ("FAIL", "\033[31m"),
    "timed-out": ("TIME", "\033[35m"),
    "terminated": ("KILL", "\033[31m"),
}
_RESET = "\033[0m"


def _style(verdict: str, use_colour: bool):
    glyph, colour = _VERDICT_STYLE.get(verdict, ("?  ", ""))
    if not use_colour:
        colour = ""
        return glyph, colour, ""
    return glyph, colour, _RESET


# ----------------------------------------------------------------------------
# renderers
# ----------------------------------------------------------------------------
def render_show(t: dict, use_colour: bool = True) -> str:
    glyph, c, r = _style(t["verdict"], use_colour)
    L = []
    L.append(f"{c}[{glyph}]{r} {t['id']}  {t['label']}")
    L.append(f"     verdict : {c}{t['verdict']}{r} — {t['reason']}")
    L.append(f"     cmd     : {t['cmd'][:120]}")
    L.append(f"     timing  : {_fmt_dur(t['duration_s'])} run"
             + (f" / {_fmt_dur(t['timeout_s'])} ceiling" if t['timeout_s'] else "")
             + (f"  |  STALLED {_fmt_dur(t['stall_s'])} before end" if t['stall_s'] else ""))
    L.append(f"     exit    : rc={t['rc']}  status={t['status']}")
    line = f"     log     : {t['log_lines']} lines"
    line += f"  |  {t['error_count']} error line(s)"
    line += f"  |  {t['retries']} retry marker(s)"
    if t["http_errors"]:
        line += f"  |  {t['http_errors']} HTTP 429/5xx"
    L.append(line)
    if t["models"]:
        L.append(f"     models  : {', '.join(t['models'])}")
    econ = []
    if t["tokens"] is not None:
        econ.append(f"{t['tokens']:,} tokens")
    if t["cost_usd"] is not None:
        econ.append(f"${t['cost_usd']:.4f}")
    if econ:
        L.append(f"     economics: {'  |  '.join(econ)}")
    if t["error_lines"]:
        L.append(f"     first errors:")
        for e in t["error_lines"][:5]:
            L.append(f"       {c}·{r} {e}")
    return "\n".join(L)


def render_list(traces: list[dict], use_colour: bool = True) -> str:
    L = []
    L.append(f"{'':1} {'JOB ID':<17} {'VERDICT':<16} {'DUR':>7} {'ERR':>4} {'RTY':>4}  LABEL")
    L.append("-" * 92)
    for t in traces:
        glyph, c, r = _style(t["verdict"], use_colour)
        L.append(
            f"{c}{glyph:<4}{r} {t['id']:<17} {c}{t['verdict']:<16}{r} "
            f"{_fmt_dur(t['duration_s']):>7} {t['error_count']:>4} {t['retries']:>4}  "
            f"{t['label'][:40]}"
        )
    return "\n".join(L)


def render_stats(traces: list[dict]) -> str:
    n = len(traces)
    if not n:
        return "no jobs on disk"
    from collections import Counter
    verdicts = Counter(t["verdict"] for t in traces)
    ok = verdicts.get("ok", 0)
    failed = sum(verdicts.get(v, 0) for v in ("failed", "terminated", "timed-out"))
    tokens = sum(t["tokens"] or 0 for t in traces)
    cost = sum(t["cost_usd"] or 0 for t in traces)
    L = [f"{n} jobs on disk"]
    L.append(f"  success   : {ok}/{n} ({100*ok//n}% clean exit)")
    L.append(f"  failing   : {failed}  " + ", ".join(f"{v}={verdicts[v]}" for v in ("failed", "terminated", "timed-out") if verdicts.get(v)))
    if tokens:
        L.append(f"  tokens    : {tokens:,} mined from logs")
    if cost:
        L.append(f"  cost      : ${cost:.2f} mined from logs")
    return "\n".join(L)


# ----------------------------------------------------------------------------
# Phoenix emit — append spans to the shipper spool; the running shipper
# (ship_spans.py) drains them to Phoenix on its next tick. No new infra.
# ----------------------------------------------------------------------------
def _clip(v, n=4000):
    try:
        s = v if isinstance(v, str) else json.dumps(v, default=str)
    except Exception:
        s = str(v)
    return s[:n]


def to_spans(t: dict) -> list[dict]:
    """One CHAIN span per job + child TOOL spans for mined incidents."""
    jid = t["id"]
    tid = _trace_id(jid)
    start = t["start_ns"] or _now_ns()
    end = t["end_ns"] or start
    if end <= start:
        end = start + 1_000_000  # 1ms floor so Phoenix renders a bar
    is_error = t["verdict"] in ("failed", "terminated", "timed-out", "done-with-errors")
    root = {
        "trace_id": tid,
        "span_id": _span_id(jid, "root"),
        "parent_span_id": None,
        "name": f"bobjob:{t['label'][:48] or jid}",
        "start_ns": start,
        "end_ns": end,
        "kind": "CHAIN",
        "status_error": is_error,
        "attrs": {
            "openinference.span.kind": "CHAIN",
            "service.name": "bob-bg",
            "job.id": jid,
            "job.verdict": t["verdict"],
            "job.reason": t["reason"],
            "job.rc": t["rc"],
            "job.duration_s": t["duration_s"],
            "job.cmd": _clip(t["cmd"], 1000),
            "job.error_count": t["error_count"],
            "job.retries": t["retries"],
            "job.http_errors": t["http_errors"],
            "job.models": ", ".join(t["models"]),
            "job.tokens": t["tokens"] if t["tokens"] is not None else "",
            "job.cost_usd": t["cost_usd"] if t["cost_usd"] is not None else "",
        },
    }
    spans = [root]
    # spread mined error lines as child markers across the job window so a
    # failing run reads as a timeline in Phoenix, not just a red bar.
    errs = t["error_lines"][:10]
    if errs:
        span_len = max(1_000_000, (end - start) // (len(errs) + 1))
        for i, e in enumerate(errs, 1):
            s0 = start + span_len * i
            spans.append({
                "trace_id": tid,
                "span_id": _span_id(jid, f"err:{i}"),
                "parent_span_id": _span_id(jid, "root"),
                "name": "error",
                "start_ns": s0,
                "end_ns": s0 + 1_000_000,
                "kind": "TOOL",
                "status_error": True,
                "attrs": {
                    "openinference.span.kind": "TOOL",
                    "job.id": jid,
                    "output.error": _clip(e, 1000),
                },
            })
    return spans


def emit(job_ids: list[str], spool: str = SPOOL) -> int:
    os.makedirs(os.path.dirname(spool), exist_ok=True)
    written = 0
    with open(spool, "a") as f:
        for jid in job_ids:
            try:
                for sp in to_spans(build_trace(jid)):
                    f.write(json.dumps(sp) + "\n")
                    written += 1
            except Exception as ex:
                sys.stderr.write(f"[bob-trace] skip {jid}: {ex}\n")
    return written


# ----------------------------------------------------------------------------
# HTML trace card — self-contained, Workloft house style (#FA3E33 on #181818)
# ----------------------------------------------------------------------------
def render_html(t: dict) -> str:
    e = _html.escape
    colour = {
        "ok": "#3fb950", "done-with-errors": "#d29922", "running": "#58a6ff",
        "failed": "#FA3E33", "terminated": "#FA3E33", "timed-out": "#bc8cff",
    }.get(t["verdict"], "#9a9a9a")

    def chip(label, value):
        return (f'<div class="chip"><div class="k">{e(label)}</div>'
                f'<div class="v">{e(str(value))}</div></div>')

    chips = [
        chip("Duration", _fmt_dur(t["duration_s"])),
        chip("Exit", f"rc={t['rc']}"),
        chip("Log lines", f"{t['log_lines']:,}"),
        chip("Error lines", t["error_count"]),
        chip("Retry markers", t["retries"]),
    ]
    if t["http_errors"]:
        chips.append(chip("HTTP 429/5xx", t["http_errors"]))
    if t["tokens"] is not None:
        chips.append(chip("Tokens", f"{t['tokens']:,}"))
    if t["cost_usd"] is not None:
        chips.append(chip("Cost", f"${t['cost_usd']:.4f}"))
    if t["stall_s"]:
        chips.append(chip("Heartbeat stall", _fmt_dur(t["stall_s"])))

    errs = "".join(f'<li>{e(x)}</li>' for x in t["error_lines"][:8])
    errs_block = (f'<div class="sec"><div class="sech">First error lines</div>'
                  f'<ul class="errs">{errs}</ul></div>') if errs else ""
    models_block = (f'<div class="sec"><div class="sech">Models seen</div>'
                    f'<div class="models">{e(", ".join(t["models"]))}</div></div>') if t["models"] else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bob-trace · {e(t['id'])}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0e0e0e; color:#e8e8e8;
    font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:0 0 48px; }}
  .band {{ background:#181818; padding:18px 28px; display:flex; align-items:baseline; justify-content:space-between; }}
  .band .logo {{ font-weight:700; letter-spacing:.02em; }}
  .band .eyebrow {{ color:#9a9a9a; text-transform:uppercase; letter-spacing:.14em; font-size:11px; }}
  .rule {{ height:3px; background:#FA3E33; }}
  .body {{ padding:28px; }}
  .verdict {{ display:inline-block; padding:4px 12px; border-radius:2mm; font-weight:700;
    text-transform:uppercase; letter-spacing:.08em; font-size:12px;
    color:#0e0e0e; background:{colour}; }}
  h1 {{ font-size:20px; margin:14px 0 4px; }}
  .reason {{ color:#b9b9b9; margin:0 0 18px; }}
  .cmd {{ font-family:"Courier New",monospace; font-size:12.5px; background:#161616;
    border:1px solid #262626; border-left:3px solid {colour}; border-radius:2mm;
    padding:12px 14px; color:#cfcfcf; overflow-x:auto; white-space:pre-wrap; word-break:break-word; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:10px; margin:20px 0; }}
  .chip {{ background:#161616; border:1px solid #262626; border-top:1.3mm solid {colour};
    border-radius:2mm; padding:10px 14px; min-width:104px; }}
  .chip .k {{ color:#9a9a9a; font-size:11px; text-transform:uppercase; letter-spacing:.08em; }}
  .chip .v {{ font-size:19px; font-weight:700; margin-top:3px; }}
  .sec {{ margin-top:22px; }}
  .sech {{ color:#9a9a9a; text-transform:uppercase; letter-spacing:.12em; font-size:11px; margin-bottom:8px; }}
  .errs {{ margin:0; padding-left:18px; }}
  .errs li {{ font-family:"Courier New",monospace; font-size:12px; color:#e0b0ab; margin:3px 0; word-break:break-word; }}
  .models {{ font-family:"Courier New",monospace; font-size:13px; color:#cfcfcf; }}
  .foot {{ color:#6a6a6a; font-size:11px; margin-top:28px; border-top:1px solid #222; padding-top:12px; }}
</style></head><body><div class="wrap">
  <div class="band"><span class="logo">Workloft</span><span class="eyebrow">bob-trace · fleet run</span></div>
  <div class="rule"></div>
  <div class="body">
    <span class="verdict">{e(t['verdict'])}</span>
    <h1>{e(t['id'])} &nbsp;<span style="color:#9a9a9a;font-weight:400;font-size:15px">{e(t['label'])}</span></h1>
    <p class="reason">{e(t['reason'])}</p>
    <div class="cmd">{e(t['cmd'])}</div>
    <div class="chips">{''.join(chips)}</div>
    {models_block}
    {errs_block}
    <div class="foot">Trace derived post-hoc from the bob-bg job record and log. No agent hooks fired inside this job.</div>
  </div>
</div></body></html>"""


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _all_job_ids() -> list[str]:
    ids = []
    for p in glob.glob(os.path.join(JOBS_DIR, "*.json")):
        ids.append(os.path.splitext(os.path.basename(p))[0])
    return sorted(ids)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bob-trace", description="Inspectable traces for detached bob-bg jobs.")
    sub = ap.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="recent jobs, health at a glance")
    p_list.add_argument("-n", type=int, default=20)

    p_show = sub.add_parser("show", help="full trace for one job")
    p_show.add_argument("id")

    p_html = sub.add_parser("html", help="render a self-contained HTML trace card")
    p_html.add_argument("id")
    p_html.add_argument("-o", "--out", default=None)

    p_emit = sub.add_parser("emit", help="pipe job(s) into Phoenix via the shipper spool")
    p_emit.add_argument("id", nargs="?")
    p_emit.add_argument("--all", action="store_true")

    sub.add_parser("stats", help="fleet-wide summary across all jobs")

    args = ap.parse_args(argv)
    use_colour = sys.stdout.isatty()

    if args.cmd == "list" or args.cmd is None:
        n = getattr(args, "n", 20)
        ids = _all_job_ids()[-n:][::-1]
        traces = [build_trace(i) for i in ids]
        print(render_list(traces, use_colour))
        return 0

    if args.cmd == "show":
        print(render_show(build_trace(args.id), use_colour))
        return 0

    if args.cmd == "html":
        out = args.out or f"/tmp/bob-trace-{args.id}.html"
        with open(out, "w") as f:
            f.write(render_html(build_trace(args.id)))
        print(out)
        return 0

    if args.cmd == "emit":
        ids = _all_job_ids() if args.all else ([args.id] if args.id else [])
        if not ids:
            print("nothing to emit: pass an <id> or --all", file=sys.stderr)
            return 2
        n = emit(ids)
        print(f"appended {n} spans for {len(ids)} job(s) -> spool "
              f"(shipper drains to Phoenix within ~3s)")
        return 0

    if args.cmd == "stats":
        traces = [build_trace(i) for i in _all_job_ids()]
        print(render_stats(traces))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
