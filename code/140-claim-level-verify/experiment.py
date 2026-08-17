#!/usr/bin/env python3
"""
experiment.py — does claim-level refutation verify reasoning better than a single
holistic adversarial pass, and at what token cost?

Two verifiers, same model (Haiku), temperature 0, same hand-authored labelled set:

  A) HOLISTIC   — one call: "adversarially check this whole trace, is it sound?"
                  This is the shape of a normal single-pass verify.
  B) CLR        — claim-level refutation (after the CLR arXiv paper 2608.11994):
                  1. decompose the trace into decision-critical claims
                  2. for EACH claim, an isolated call that sees only the problem
                     and that one claim, told to find a single decisive flaw
                  the trace is flawed if any critical claim is decisively refuted.
                  The isolation is the point: a refuter chasing one claim can't be
                  soothed by the surrounding confident prose.

Ground truth is hand-authored so no model grades the traces. Every flawed trace
has ONE decisive flaw. Real token counts from the API, no fabrication. Small n by
design — this is a spike, and the writeup says so.

    python3 experiment.py            # runs live, writes result.json
    python3 experiment.py --dry      # prints the labelled set, no API calls
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/home/workloft/ruby")
import ruby  # noqa: E402

# Verifier model. We route to Gemini Flash via the Google key rather than a Claude
# model only because our prepaid Anthropic API pool is empty (the Claude Code
# subscription is a separate path we can't drive programmatically). The holistic
# vs claim-level comparison is model-agnostic; both verifiers use the SAME model,
# so the comparison is fair. Reported honestly in the writeup.
MODEL = "gemini-2.5-flash"
_GKEY = ruby._KEYS["google"]

# ---------------------------------------------------------------------------
# Labelled set. Each flawed trace carries exactly one decisive error; each sound
# trace is genuinely correct. label: "flawed" means the reasoning/answer is wrong.
# ---------------------------------------------------------------------------
TRACES = [
    # --- FLAWED (one decisive error each) ---
    {"id": "pens", "label": "flawed",
     "problem": "A shop sells pens at £2 each with 15% off orders over 10 pens. What does an order of 12 pens cost?",
     "trace": "12 pens at £2 is 12 x 2 = £24. The order is over 10 so 15% off applies. "
              "15% of 24 is 4.60. So the total is 24 - 4.60 = £19.40. ANSWER: £19.40",
     "flaw": "15% of 24 is 3.60, not 4.60; correct total is £20.40."},
    {"id": "aquatic", "label": "flawed",
     "problem": "All cats are mammals. Some mammals are aquatic. Does it follow that some cats are aquatic?",
     "trace": "All cats are mammals, so cats are a kind of mammal. Some mammals are aquatic. "
              "Since cats are mammals and some mammals are aquatic, some cats are aquatic. ANSWER: yes",
     "flaw": "Invalid syllogism; the aquatic mammals need not be the cats."},
    {"id": "carspeed", "label": "flawed",
     "problem": "A car travels 150 miles in 2.5 hours. What is its average speed in mph?",
     "trace": "Average speed is distance divided by time. 150 divided by 2.5. "
              "150 / 2.5 = 55. So the average speed is 55 mph. ANSWER: 55",
     "flaw": "150 / 2.5 = 60, not 55."},
    {"id": "seq", "label": "flawed",
     "problem": "What is the next number in the sequence 3, 6, 11, 18, 27, ?",
     "trace": "Look at the differences: 6-3=3, 11-6=5, 18-11=7, 27-18=9. The differences go up by 2. "
              "The differences are constant at 3, so the next term is 27 + 3 = 30. ANSWER: 30",
     "flaw": "It states the differences go up by 2 then contradicts itself; next diff is 11, so 38."},
    {"id": "choose", "label": "flawed",
     "problem": "How many ways can you choose 2 items from 5?",
     "trace": "This is a combination, 5 choose 2. The formula is 5! / 2!. "
              "5! = 120 and 2! = 2, so 120 / 2 = 60. ANSWER: 60",
     "flaw": "Dropped the (5-2)! term; 5 choose 2 = 10."},
    {"id": "percent", "label": "flawed",
     "problem": "80 is what percentage of 200?",
     "trace": "Percentage is the part over the whole. 80 / 200 = 0.4. "
              "As a percentage that is 4%. ANSWER: 4%",
     "flaw": "0.4 is 40%, not 4%."},
    {"id": "primes", "label": "flawed",
     "problem": "Is 91 a prime number?",
     "trace": "Check small divisors. 91 is odd so not divisible by 2. 9+1=10 not divisible by 3. "
              "It does not end in 0 or 5. It is not divisible by 7. So 91 is prime. ANSWER: yes",
     "flaw": "91 = 7 x 13, so it is not prime; the divisible-by-7 check is wrong."},

    # --- SOUND (genuinely correct) ---
    {"id": "discount2", "label": "sound",
     "problem": "A jacket costs £80 and is reduced by 25%. What is the sale price?",
     "trace": "25% of 80 is 0.25 x 80 = 20. Subtract from the original: 80 - 20 = 60. ANSWER: £60",
     "flaw": ""},
    {"id": "syllogism2", "label": "sound",
     "problem": "All Bloops are Razzies. All Razzies are Lazzies. Are all Bloops necessarily Lazzies?",
     "trace": "Every Bloop is a Razzie. Every Razzie is a Lazzie. So following the chain, every Bloop "
              "is a Lazzie. ANSWER: yes",
     "flaw": ""},
    {"id": "speed2", "label": "sound",
     "problem": "A train covers 60 km in 45 minutes. What is its speed in km/h?",
     "trace": "45 minutes is 0.75 hours. Speed is distance over time: 60 / 0.75 = 80. ANSWER: 80 km/h",
     "flaw": ""},
    {"id": "sum2", "label": "sound",
     "problem": "What is the sum of the first 5 positive even numbers?",
     "trace": "The first 5 positive even numbers are 2, 4, 6, 8, 10. Their sum is 2+4+6+8+10 = 30. ANSWER: 30",
     "flaw": ""},
    {"id": "binary2", "label": "sound",
     "problem": "Convert binary 1011 to decimal.",
     "trace": "1011 is 1x8 + 0x4 + 1x2 + 1x1 = 8 + 0 + 2 + 1 = 11. ANSWER: 11",
     "flaw": ""},
    {"id": "choose2", "label": "sound",
     "problem": "How many ways can you choose 3 items from 4?",
     "trace": "4 choose 3 = 4! / (3! x 1!) = 24 / 6 = 4. ANSWER: 4",
     "flaw": ""},
    {"id": "prime2", "label": "sound",
     "problem": "Is 97 a prime number?",
     "trace": "Test divisors up to sqrt(97) which is under 10. 97 is odd, not divisible by 3 (digits sum to 16), "
              "not by 5, not by 7 (7x13=91, 7x14=98). No divisor found, so 97 is prime. ANSWER: yes",
     "flaw": ""},
]


def call(prompt, max_tokens=600, _retries=3):
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={_GKEY}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    last = None
    for attempt in range(_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise last
    text = ""
    cands = data.get("candidates", [])
    if cands:
        for p in cands[0].get("content", {}).get("parts", []):
            text += p.get("text", "")
    u = data.get("usageMetadata", {})
    tin = u.get("promptTokenCount", 0)
    # count hidden thinking tokens as output, so the cost comparison is honest
    tout = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
    return text.strip(), tin, tout


# ---- Verifier A: holistic ----
def holistic(tr):
    prompt = (
        "You are an adversarial checker. Read this problem and a proposed reasoning "
        "trace. Find any flaw. Decide if the trace's reasoning and final answer are "
        "SOUND or FLAWED.\n\n"
        f"PROBLEM: {tr['problem']}\n\nTRACE: {tr['trace']}\n\n"
        "Reply with exactly one line: 'VERDICT: SOUND' or 'VERDICT: FLAWED'."
    )
    txt, tin, tout = call(prompt, max_tokens=400)
    flawed = "FLAWED" in txt.upper()
    return ("flawed" if flawed else "sound"), tin, tout


# ---- Verifier B: claim-level refutation ----
def decompose(tr):
    prompt = (
        "Break this reasoning trace into its decision-critical claims: the load-bearing "
        "steps whose truth the final answer depends on. List each as one short line. "
        "Ignore restating the question or the final answer line.\n\n"
        f"PROBLEM: {tr['problem']}\n\nTRACE: {tr['trace']}\n\n"
        "Output only the claims, one per line, no numbering."
    )
    txt, tin, tout = call(prompt, max_tokens=400)
    claims = [re.sub(r"^[-*\d.\)\s]+", "", ln).strip()
              for ln in txt.splitlines() if ln.strip()]
    return [c for c in claims if len(c) > 3][:6], tin, tout


def refute(problem, claim):
    # Isolation: the refuter sees only the problem and this one claim.
    prompt = (
        "You are trying to REFUTE a single claim made while solving a problem. "
        "Look only at this claim. If it contains a decisive error (arithmetic, logical, "
        "or factual), refute it. If it is correct, say so. Do not be charitable.\n\n"
        f"PROBLEM: {problem}\n\nCLAIM: {claim}\n\n"
        "Reply with exactly one line: 'REFUTED: YES' or 'REFUTED: NO'."
    )
    txt, tin, tout = call(prompt, max_tokens=200)
    return ("REFUTED: YES" in txt.upper() or re.search(r"\bREFUTED:\s*YES", txt.upper()) is not None), tin, tout


def clr(tr):
    tin_tot = tout_tot = 0
    claims, tin, tout = decompose(tr)
    tin_tot += tin; tout_tot += tout
    any_refuted = False
    refuted_claim = ""
    for c in claims:
        r, tin, tout = refute(tr["problem"], c)
        tin_tot += tin; tout_tot += tout
        if r:
            any_refuted = True
            refuted_claim = c
            break  # one decisive refutation is enough
    return ("flawed" if any_refuted else "sound"), tin_tot, tout_tot, len(claims), refuted_claim


def main():
    if "--dry" in sys.argv:
        for t in TRACES:
            print(f"[{t['label']:6}] {t['id']:11} {t['problem'][:60]}")
        print(f"\n{len(TRACES)} traces "
              f"({sum(1 for t in TRACES if t['label']=='flawed')} flawed, "
              f"{sum(1 for t in TRACES if t['label']=='sound')} sound)")
        return

    rows = []
    agg = {"holistic": {"tin": 0, "tout": 0}, "clr": {"tin": 0, "tout": 0}}
    for t in TRACES:
        h_pred, h_tin, h_tout = holistic(t)
        c_pred, c_tin, c_tout, nclaims, refc = clr(t)
        agg["holistic"]["tin"] += h_tin; agg["holistic"]["tout"] += h_tout
        agg["clr"]["tin"] += c_tin; agg["clr"]["tout"] += c_tout
        rows.append({"id": t["id"], "truth": t["label"],
                     "holistic": h_pred, "clr": c_pred,
                     "clr_claims": nclaims, "clr_refuted": refc})
        print(f"  {t['id']:11} truth={t['label']:6}  holistic={h_pred:6}  clr={c_pred:6}  "
              f"({nclaims} claims)")

    def stats(key):
        tp = sum(1 for r in rows if r["truth"] == "flawed" and r[key] == "flawed")
        fn = sum(1 for r in rows if r["truth"] == "flawed" and r[key] == "sound")
        fp = sum(1 for r in rows if r["truth"] == "sound" and r[key] == "flawed")
        tn = sum(1 for r in rows if r["truth"] == "sound" and r[key] == "sound")
        n = len(rows)
        return {"caught": tp, "missed": fn, "false_alarms": fp, "correct_sound": tn,
                "recall_on_flawed": round(tp / (tp + fn), 3) if (tp + fn) else None,
                "accuracy": round((tp + tn) / n, 3)}

    result = {
        "model": MODEL, "n_traces": len(TRACES),
        "flawed": sum(1 for t in TRACES if t["label"] == "flawed"),
        "sound": sum(1 for t in TRACES if t["label"] == "sound"),
        "holistic": {**stats("holistic"), "tokens_in": agg["holistic"]["tin"],
                     "tokens_out": agg["holistic"]["tout"],
                     "tokens_total": agg["holistic"]["tin"] + agg["holistic"]["tout"]},
        "clr": {**stats("clr"), "tokens_in": agg["clr"]["tin"],
                "tokens_out": agg["clr"]["tout"],
                "tokens_total": agg["clr"]["tin"] + agg["clr"]["tout"]},
        "rows": rows,
    }
    Path("result.json").write_text(json.dumps(result, indent=2))

    print("\n  === RESULT ===")
    for k in ("holistic", "clr"):
        s = result[k]
        print(f"  {k:9}  recall_on_flawed={s['recall_on_flawed']}  accuracy={s['accuracy']}  "
              f"false_alarms={s['false_alarms']}  tokens={s['tokens_total']}")
    print("\n  wrote result.json")


if __name__ == "__main__":
    main()
