#!/usr/bin/env python3
"""A/B: can Claude Haiku 5.5 replace the fleet's cheap tiers on real work?

Loop build (2026-10-17, Alfred "/go on Haiku test"). Haiku 5.5 launched 7 Oct 2026
at $0.10 in / $0.50 out per M tokens (prompts <100K). Two real fleet jobs, real
inputs, current production prompts:

  WALT  (category=classify, tier=cheap)  Agentic Oddities first-pass scoring.
        141 real candidates from the 2026-10-16 run. Incumbent: Gemini 2.5 Flash.
        Reference marks: Claude Opus 5 (high effort) on the same prompt.
        Metrics: JSON validity, mean |score - ref|, shortlist (score >= 6) F1 vs ref.

  VERA  (category=reason_hard, tier=balanced)  Agentic Oddities editor picks.
        3 real shortlists (2026-10-10, -13, -16). Incumbent: DeepSeek V4 Pro.
        Blind judge: Claude Opus 5 scores each arm 1-10 on grounding, picks, angles.

Arms per job: incumbent, Haiku 5.5 effort=low, Haiku 5.5 effort=high.
Incumbents run via OpenRouter so cost is the provider-reported figure; Claude
runs direct, costed from returned usage at list price.

Run from /home/workloft/ruby:  python3 bench_haiku55_cheap_tier.py [--walt-n N]
Writes haiku55_cheap_tier_result.json (+ raw outputs) next to this file.
"""
import concurrent.futures as cf
import json, os, pathlib, random, re, sys, time
import urllib.request as urlreq

import anthropic
import ruby

sys.path.insert(0, "/home/workloft/research/agentic-oddities")
import agentic_oddities as AO  # SCORE_SYSTEM, VERA_SYSTEM, prompt builders

HERE = pathlib.Path(__file__).parent
DATA = pathlib.Path("/home/workloft/research/agentic-oddities/data")
OUT = HERE / "haiku55_cheap_tier_result.json"
RAW = HERE / "haiku55_cheap_tier_raw.json"

ruby._KEYS = ruby._load_keys()
OR_KEY = ruby._KEYS["openrouter"]
CLAUDE = anthropic.Anthropic(api_key=ruby._KEYS["anthropic"], max_retries=4)

PRICE = {  # $ per M tokens, list price, prompts < 100K
    "gemini-2.5-flash": (0.30, 2.50),  # Google list price (Ruby's catalog still says 0.075/0.30)
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5": (5.00, 25.00),
}
HAIKU = "claude-haiku-5-5"
REF = "claude-opus-5"


def _strip(s):
    return re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", (s or "").strip(), flags=re.M)


def call_openrouter(slug, prompt, max_tokens, temperature):
    body = json.dumps({"model": slug, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temperature,
                       "usage": {"include": True}}).encode()
    req = urlreq.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(4):
        try:
            with urlreq.urlopen(req, timeout=180) as r:
                d = json.load(r)
            break
        except Exception as e:
            if attempt == 3:
                return {"text": "", "error": str(e)[:200], "cost": 0, "in": 0, "out": 0, "secs": time.time() - t0}
            time.sleep(3 * (attempt + 1))
    u = d.get("usage", {})
    text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"text": text, "cost": float(u.get("cost") or 0), "in": u.get("prompt_tokens", 0),
            "out": u.get("completion_tokens", 0), "secs": time.time() - t0}


def call_google(prompt, max_tokens, temperature):
    """Gemini 2.5 Flash direct, exactly as Ruby's _google_chat calls it (thinkingBudget=0)."""
    key = ruby._KEYS["google"]
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                       "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature,
                                            "thinkingConfig": {"thinkingBudget": 0}}}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    t0 = time.time()
    for attempt in range(4):
        try:
            with urlreq.urlopen(urlreq.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=120) as r:
                d = json.load(r)
            break
        except Exception as e:
            if attempt == 3:
                return {"text": "", "error": str(e)[:200], "cost": 0, "in": 0, "out": 0, "secs": time.time() - t0}
            time.sleep(3 * (attempt + 1))
    u = d.get("usageMetadata", {})
    parts = ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    i, o = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
    pi, po = PRICE["gemini-2.5-flash"]
    return {"text": text, "cost": (i * pi + o * po) / 1e6, "in": i, "out": o, "secs": time.time() - t0}


def call_claude(model, prompt, max_tokens, effort, temperature=None):
    kw = dict(model=model, max_tokens=max_tokens, output_config={"effort": effort},
              messages=[{"role": "user", "content": prompt}])
    t0 = time.time()
    try:
        r = CLAUDE.messages.create(**kw)
    except Exception as e:
        return {"text": "", "error": str(e)[:200], "cost": 0, "in": 0, "out": 0, "secs": time.time() - t0}
    text = "".join(b.text for b in r.content if b.type == "text")
    pi, po = PRICE[model]
    cost = (r.usage.input_tokens * pi + r.usage.output_tokens * po) / 1e6
    return {"text": text, "cost": cost, "in": r.usage.input_tokens, "out": r.usage.output_tokens,
            "secs": time.time() - t0, "stop": r.stop_reason}


# ---------------------------------------------------------------- WALT
def walt_prompt(c):
    src = ""
    if c.get("points"):
        src += f"  upvotes/points: {c['points']}\n"
    if c.get("comments"):
        src += f"  comments: {c['comments']}\n"
    if c.get("preexisting_score"):
        src += f"  arxiv-watch score: {c['preexisting_score']}/10\n"
    body = (f"Source: {c['source']}\n{src}Title: {c['title']}\n\n"
            f"Summary/description:\n{(c.get('summary') or '')[:2000] or '(none — title-only)'}")
    return AO.SCORE_SYSTEM + "\n\n" + body


def parse_score(text):
    t = _strip(text)
    try:
        return int(json.loads(t).get("score"))
    except Exception:
        m = re.search(r"\"score\"\s*:\s*(\d+)", t)
        return int(m.group(1)) if m else None


WALT_ARMS = {
    "gemini-2.5-flash (incumbent)": lambda p: call_google(p, 300, 0.0),
    "haiku-5.5 low": lambda p: call_claude(HAIKU, p, 300, "low"),
    "haiku-5.5 high": lambda p: call_claude(HAIKU, p, 3000, "high"),
    "REF opus-5 high": lambda p: call_claude(REF, p, 4000, "high"),
}


def run_walt(n, only=None):
    cands = json.load(open(DATA / "oddities-2026-10-16.json"))[:n]
    prompts = [walt_prompt(c) for c in cands]
    res = {}
    for arm, fn in WALT_ARMS.items():
        if only and arm not in only:
            continue
        with cf.ThreadPoolExecutor(8) as ex:
            res[arm] = list(ex.map(fn, prompts))
        print(f"walt {arm}: done", flush=True)
    ref = [parse_score(r["text"]) for r in res["REF opus-5 high"]]
    ref_short = {i for i, s in enumerate(ref) if s is not None and s >= 6}
    summary = {}
    for arm, rows in res.items():
        sc = [parse_score(r["text"]) for r in rows]
        valid = [i for i, s in enumerate(sc) if s is not None]
        pairs = [(sc[i], ref[i]) for i in valid if ref[i] is not None]
        mae = sum(abs(a - b) for a, b in pairs) / len(pairs) if pairs else None
        short = {i for i in valid if sc[i] >= 6}
        tp = len(short & ref_short)
        prec = tp / len(short) if short else 0
        rec = tp / len(ref_short) if ref_short else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        summary[arm] = {
            "n": len(rows), "json_valid": len(valid), "mae_vs_ref": round(mae, 2) if mae is not None else None,
            "shortlist_size": len(short), "ref_shortlist_size": len(ref_short),
            "shortlist_precision": round(prec, 2), "shortlist_recall": round(rec, 2), "shortlist_f1": round(f1, 2),
            "cost_usd": round(sum(r["cost"] for r in rows), 4),
            "in_tokens": sum(r["in"] for r in rows), "out_tokens": sum(r["out"] for r in rows),
            "median_secs": round(sorted(r["secs"] for r in rows)[len(rows) // 2], 2),
            "errors": sum(1 for r in rows if r.get("error")),
        }
    return summary, {arm: [{"title": c["title"], "score": parse_score(r["text"]), "raw": r["text"][:300]}
                           for c, r in zip(cands, rows)] for arm, rows in res.items()}


# ---------------------------------------------------------------- VERA
VERA_DAYS = ["2026-10-10", "2026-10-13", "2026-10-16"]
VERA_ARMS = {
    "deepseek-v4-pro (incumbent)": lambda p: call_openrouter("deepseek/deepseek-v4-pro", p, 2200, 0.3),
    "haiku-5.5 low": lambda p: call_claude(HAIKU, p, 4000, "low"),
    "haiku-5.5 high": lambda p: call_claude(HAIKU, p, 12000, "high"),
}

JUDGE = """You are a strict, blind judge comparing editor outputs for "Agentic Oddities", a digest of real AI-agent incident stories.
Below: the candidate list the editors saw, then {k} anonymised editor outputs (labelled {labels}).
The editors were told: pick the best real incident + 3 honourable mentions, write a grounded one-paragraph "news angle" for each, NEVER invent facts (names, numbers, dates, mechanisms) not present in the candidate's title/summary, kill weak candidates, and return valid JSON.

Score EACH output 1-10 on:
  grounding: 10 = every claim traceable to the candidate text; heavy penalty for any invented fact or asserted mechanism the source doesn't state.
  picks: are the headline and mentions the strongest real incidents in the list?
  angles: are the news angles sharp, specific, useful to a writer?
  format: valid JSON, all required fields, UK English.
Then an overall 1-10 (grounding weighs most).

Return JSON only:
{{"scores": {{"<label>": {{"grounding": int, "picks": int, "angles": int, "format": int, "overall": int, "note": "one sentence"}}, ...}}}}

=== CANDIDATES ===
{cands}

=== OUTPUTS ===
{outs}"""


def run_vera():
    raw, judged = {}, []
    for day in VERA_DAYS:
        shortlist = json.load(open(DATA / f"oddities-{day}.shortlist.json"))
        listing = []
        for i, c in enumerate(shortlist):
            s = c.get("scored") or {}
            listing.append(
                f"[{i}] source={c['source']} score={s.get('score','?')}/10 kind={s.get('kind','?')}\n"
                f"    title: {c['title']}\n    url: {c['url']}\n    walt's hook: {s.get('hook','')}\n"
                f"    signal: pts={c.get('points',0)} comments={c.get('comments',0)}\n"
                f"    summary: {(c.get('summary') or '')[:600]}\n")
        cands = "\n".join(listing)
        prompt = AO.VERA_SYSTEM + "\n\nCandidates from the past few days:\n\n" + cands
        with cf.ThreadPoolExecutor(3) as ex:
            outs = dict(zip(VERA_ARMS, ex.map(lambda f: f(prompt), VERA_ARMS.values())))
        raw[day] = outs
        arms = list(outs)
        random.Random(day).shuffle(arms)
        labels = [chr(65 + i) for i in range(len(arms))]
        blocks = "\n\n".join(f"--- OUTPUT {l} ---\n{_strip(outs[a]['text'])[:9000]}" for l, a in zip(labels, arms))
        j = call_claude(REF, JUDGE.format(k=len(arms), labels=", ".join(labels), cands=cands, outs=blocks), 8000, "high")
        try:
            sc = json.loads(_strip(j["text"]))["scores"]
        except Exception:
            m = re.search(r"\{.*\}", j["text"], re.S)
            sc = json.loads(m.group(0))["scores"] if m else {}
        judged.append({"day": day, "map": dict(zip(labels, arms)), "scores": sc, "judge_cost": j["cost"]})
        print(f"vera {day}: judged", flush=True)
    summary = {}
    for arm in VERA_ARMS:
        rows = [raw[d][arm] for d in VERA_DAYS]
        per = []
        for jd in judged:
            lab = next(l for l, a in jd["map"].items() if a == arm)
            per.append(jd["scores"].get(lab, {}))
        avg = lambda k: round(sum(p.get(k, 0) for p in per) / len(per), 1)
        summary[arm] = {
            "overall": avg("overall"), "grounding": avg("grounding"), "picks": avg("picks"),
            "angles": avg("angles"), "format": avg("format"),
            "json_valid": sum(1 for r in rows if _valid_json(r["text"])),
            "cost_usd_3_runs": round(sum(r["cost"] for r in rows), 4),
            "out_tokens": sum(r["out"] for r in rows), "median_secs": round(sorted(r["secs"] for r in rows)[1], 1),
            "judge_notes": [p.get("note", "") for p in per],
        }
    return summary, {"raw": {d: {a: o["text"] for a, o in v.items()} for d, v in raw.items()}, "judged": judged}


def _valid_json(t):
    try:
        json.loads(_strip(t))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--walt-n") + 1]) if "--walt-n" in sys.argv else 141
    t0 = time.time()
    walt_sum, walt_raw = run_walt(n)
    vera_sum, vera_raw = run_vera()
    result = {"date": time.strftime("%Y-%m-%d"), "walt": walt_sum, "vera": vera_sum,
              "wall_secs": round(time.time() - t0)}
    OUT.write_text(json.dumps(result, indent=2))
    RAW.write_text(json.dumps({"walt": walt_raw, "vera": vera_raw}, indent=1))
    print(json.dumps(result, indent=2))
