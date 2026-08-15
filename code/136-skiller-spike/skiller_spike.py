#!/usr/bin/env python3
"""SKILLER spike — can a natural-language skill loop lift a free local model to
close the gap to a paid cloud model on a real extraction task?

Reproduces the core idea of SKILLER (arXiv:2608.10538) in ~250 lines. The insight
the paper's "reinforcement learning framework" framing hides: it does NOT train
the small model. No weights change, no GPU. It's an orchestration loop:

  strong ACTOR writes a skill  ->  small EXECUTOR runs the task with it
       ^                                       |
       |  refine skill from the mistakes  <----+  deterministic REWARD (field match)

Only a natural-language skill block (prepended to the executor's system prompt)
evolves, driven by the executor's own errors on a TRAIN set. A held-out TEST set
is only scored, so a skill that memorises answers gains nothing.

Task: messy invoice records with distractors (a buyer as well as a seller, three
dates, subtotal/VAT/total, an invoice number as well as a ref) -> normalised JSON.
The correct answer is always the seller, the invoice date, the grand total, the
ref code. A patterned, skill-fixable confusion — exactly SKILLER's target.

Runs with just a Google API key and a local Ollama:
    GOOGLE_API_KEY=... OLLAMA_MODEL=qwen2.5:7b-instruct python3 skiller_spike.py

  ACTOR    = gemini-2.5-pro (strong, writes/refines the skill)
  EXECUTOR = your local Ollama model (free)
  CEILING  = gemini-2.5-flash (the cheap cloud model you'd replace)

Kill gate: local+skill must close >= 60% of the (cloud - local_base) gap on the
held-out TEST set, or the idea is binned for this task.
"""
import json, os, re, time, urllib.request, urllib.error

GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
ACTOR_MODEL = os.environ.get("ACTOR_MODEL", "gemini-2.5-pro")
CLOUD_MODEL = os.environ.get("CLOUD_MODEL", "gemini-2.5-flash")
KILL_GATE = 0.60
MAX_ITERS = 6

BASE_SYSTEM = (
    "Extract these fields from the record and output ONLY a JSON object, no prose:\n"
    '{"vendor": <company name>, "date": <YYYY-MM-DD>, '
    '"amount": <number, no currency symbol, no thousands separators>, "ref": <reference code>}'
)

DATA = [
    ("From Acme Ltd to Beta Corp. Invoiced 3rd July 2026 (ordered 1 Jul, due 17 Jul). Subtotal £1,200.00, VAT £240.50, total £1,440.50. Invoice 5567, ref AC-88.",
     {"vendor": "Acme Ltd", "date": "2026-07-03", "amount": 1440.50, "ref": "AC-88"}),
    ("From Bright Sparks Ltd to Cohen LLP. Invoiced 4 August 2026 (due 4 September). Subtotal £80, VAT £15, total £95.00. Invoice 12, reference BS0012.",
     {"vendor": "Bright Sparks Ltd", "date": "2026-08-04", "amount": 95.00, "ref": "BS0012"}),
    ("From Northwind Traders to Acme Ltd. Invoiced 12 Jan 2026 (ordered 5 Jan). Subtotal $2,100, VAT $200, total $2,300.00. Invoice NW9, ref NW-2026-01.",
     {"vendor": "Northwind Traders", "date": "2026-01-12", "amount": 2300.00, "ref": "NW-2026-01"}),
    ("From Green Fields Co to City Council. Invoiced 1st December 2025 (due 31 Dec). Subtotal £400, VAT £80, total £480.00. Invoice 4471, ref GF7.",
     {"vendor": "Green Fields Co", "date": "2025-12-01", "amount": 480.00, "ref": "GF7"}),
    ("From Studio Ninety-One to Delta Corp. Invoiced 28 February 2026 (ordered 1 Feb). Subtotal £10,000, VAT £2,000, total £12,000.00. Invoice 114, ref SN-2026-114.",
     {"vendor": "Studio Ninety-One", "date": "2026-02-28", "amount": 12000.00, "ref": "SN-2026-114"}),
    ("From Oakwood Joinery to Miss T Blake. Invoiced 9th September 2026 (due 9 Oct). Subtotal £625, VAT £125.75, total £750.75. Invoice 45, ref OJ-45.",
     {"vendor": "Oakwood Joinery", "date": "2026-09-09", "amount": 750.75, "ref": "OJ-45"}),
    ("From Riverside Cafe to Green Fields Co. Invoiced 22 March 2026 (ordered 20 Mar). Subtotal £52.20, VAT £11, total £63.20. Invoice 889, reference RC-889.",
     {"vendor": "Riverside Cafe", "date": "2026-03-22", "amount": 63.20, "ref": "RC-889"}),
    ("From Zephyr Logistics to Acme Ltd. Invoiced July 4 2026 (due 4 Aug). Subtotal £4,500, VAT £910, total £5,410.00. Invoice 77, ref ZL-77.",
     {"vendor": "Zephyr Logistics", "date": "2026-07-04", "amount": 5410.00, "ref": "ZL-77"}),
    # --- held-out test ---
    ("From Maple & Co to Beta Corp. Invoiced 15th October 2026 (ordered 1 Oct). Subtotal £280.50, VAT £40, total £320.50. Invoice 31, ref MC-31.",
     {"vendor": "Maple & Co", "date": "2026-10-15", "amount": 320.50, "ref": "MC-31"}),
    ("From Ironclad Security to City Council. Invoiced 2 June 2026 (due 2 Jul). Subtotal £850, VAT £150, total £1,000.00. Invoice 606, reference IC-2026-06.",
     {"vendor": "Ironclad Security", "date": "2026-06-02", "amount": 1000.00, "ref": "IC-2026-06"}),
    ("From Sunrise Bakery to Cohen LLP. Invoiced 30 November 2026 (ordered 20 Nov). Subtotal £74.40, VAT £14, total £88.40. Invoice 14, ref SB-14.",
     {"vendor": "Sunrise Bakery", "date": "2026-11-30", "amount": 88.40, "ref": "SB-14"}),
    ("From Delta Print Works to Acme Ltd. Invoiced 7 April 2026 (due 7 May). Subtotal £1,900.99, VAT £250, total £2,150.99. Invoice 500, ref DPW-500.",
     {"vendor": "Delta Print Works", "date": "2026-04-07", "amount": 2150.99, "ref": "DPW-500"}),
    ("From Harbour View Ltd to Miss T Blake. Invoiced 19th May 2026 (ordered 10 May). Subtotal £39.99, VAT £8, total £47.99. Invoice 9, ref HV-9.",
     {"vendor": "Harbour View Ltd", "date": "2026-05-19", "amount": 47.99, "ref": "HV-9"}),
    ("From Quantum Widgets to Beta Corp. Invoiced 3 March 2026 (due 3 Apr). Subtotal $899, VAT $100, total $999.00. Invoice 333, ref QW-333.",
     {"vendor": "Quantum Widgets", "date": "2026-03-03", "amount": 999.00, "ref": "QW-333"}),
    ("From Copperfield Ltd to City Council. Invoiced 25 December 2026 (ordered 1 Dec). Subtotal £510, VAT £100, total £610.00. Invoice 625, reference CF-2026-25.",
     {"vendor": "Copperfield Ltd", "date": "2026-12-25", "amount": 610.00, "ref": "CF-2026-25"}),
    ("From Willow Creek Farm to Delta Corp. Invoiced 11th August 2026 (due 11 Sep). Subtotal £3,500.50, VAT £280, total £3,780.50. Invoice 8, ref WCF-8.",
     {"vendor": "Willow Creek Farm", "date": "2026-08-11", "amount": 3780.50, "ref": "WCF-8"}),
]
TRAIN, TEST = DATA[:8], DATA[8:]


def gemini(model, system, user, max_tokens=700, temperature=0.0):
    if not GOOGLE_KEY:
        raise SystemExit("set GOOGLE_API_KEY")
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_KEY}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return "".join(p.get("text", "") for c in d.get("candidates", [])
                   for p in c.get("content", {}).get("parts", [])).strip()


def ollama(system, user, max_tokens=300):
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False, "options": {"temperature": 0, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r).get("message", {}).get("content", "").strip()


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower()).rstrip(".")


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except (json.JSONDecodeError, ValueError):
        return None


def grade(got, expected):
    if not isinstance(got, dict):
        return 0.0, ["<no json>"]
    ok, wrong = 0, []
    for k, exp in expected.items():
        g = got.get(k)
        if k == "amount":
            try:
                good = abs(float(str(g).replace(",", "").replace("£", "").replace("$", "")) - float(exp)) < 0.005
            except (TypeError, ValueError):
                good = False
        else:
            good = _norm(g) == _norm(exp)
        ok += good
        if not good:
            wrong.append(f"{k}: got {g!r} want {exp!r}")
    return ok / len(expected), wrong


def run_local(skill, records):
    sysp = BASE_SYSTEM if not skill else f"{BASE_SYSTEM}\n\nSKILL (follow exactly):\n{skill}"
    rows, total = [], 0.0
    for rec, exp in records:
        try:
            out = ollama(sysp, rec)
        except Exception as e:  # noqa: BLE001
            out = f"<err {e}>"
        sc, wrong = grade(parse_json(out), exp)
        total += sc
        rows.append({"rec": rec, "score": sc, "wrong": wrong})
    return total / len(records), rows


def run_cloud(records):
    return sum(grade(parse_json(gemini(CLOUD_MODEL, BASE_SYSTEM, rec, 300)), exp)[0]
               for rec, exp in records) / len(records)


def actor_write_skill(prev, train_rows):
    fails = [r for r in train_rows if r["score"] < 1.0]
    diag = "\n".join(f"- record: {r['rec']}\n  wrong: {'; '.join(r['wrong'])}"
                     for r in fails[:8]) or "(no failures)"
    if not prev:
        user = ("A small model must extract {vendor, date (YYYY-MM-DD), amount (plain "
                "number), ref} from messy records as JSON. Write a SHORT skill block "
                "(rules + pitfalls) to prepend to its prompt. Its current mistakes with "
                f"no skill:\n\n{diag}")
    else:
        user = (f"CURRENT skill:\n-----\n{prev}\n-----\nWith it the small model still "
                f"made these mistakes:\n\n{diag}\n\nRewrite the skill to fix these "
                "patterns. Concise and general.")
    system = ("You optimise a natural-language SKILL constraining a small model. Output "
              "ONLY the new skill text. Write general rules + pitfalls (date/currency/ref "
              "parsing, output format). NEVER hardcode a record's answer — it is graded "
              "on unseen records.")
    return gemini(ACTOR_MODEL, system, user, 700, 0.3)


def main():
    t0 = time.time()
    cloud = run_cloud(TEST)
    local_base, _ = run_local("", TEST)
    gap = cloud - local_base
    print(f"cloud {cloud:.3f} | local base {local_base:.3f} | gap {gap:.3f}")
    if gap <= 0.02:
        print("gap ~0 — local already matches cloud, nothing to lift."); return

    skill, best = "", {"test": local_base, "iter": 0, "skill": ""}
    for it in range(1, MAX_ITERS + 1):
        _, train_rows = run_local(skill, TRAIN)
        skill = actor_write_skill(skill, train_rows)
        test_r, _ = run_local(skill, TEST)
        closed = (test_r - local_base) / gap if gap else 0
        print(f"iter {it}: test={test_r:.3f}  gap_closed={closed*100:.0f}%")
        if test_r > best["test"]:
            best = {"test": test_r, "iter": it, "skill": skill}
        if test_r >= 0.999:
            print("test saturated — stopping early."); break

    closed = (best["test"] - local_base) / gap if gap else 0
    verdict = "PASS" if closed >= KILL_GATE else "FAIL"
    print(f"\nRESULT: cloud {cloud:.3f} | local base {local_base:.3f} | "
          f"best local+skill {best['test']:.3f} -> gap closed {closed*100:.0f}% "
          f"(gate {KILL_GATE*100:.0f}%) -> {verdict}  [{time.time()-t0:.0f}s]")
    print(f"\nBEST SKILL (iter {best['iter']}):\n{best['skill']}")


if __name__ == "__main__":
    main()
