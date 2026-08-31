#!/usr/bin/env python3
"""
router_bench.py — test the "route to the cheap model and save 40-70%" claim.

Model routers (workweave/router and the whole category) promise big savings by
sending each prompt to the cheapest model that can handle it. The savings number
is always quoted without the other half: what it costs you in quality. This
measures both, on a realistic mix, with real calls and real token usage.

Here the cheap tier is a FREE local model (qwen2.5:7b via Ollama, marginal API
cost 0) and the premium tier is a paid API model (Llama 3.3 70B via Together).
That is the honest version of the tokenomics pitch: a lot of agent work does not
need a paid frontier call at all.

Three conditions over the same prompts:
  - all-premium : send everything to the paid model (the safe default)
  - all-cheap   : send everything to the free local model (the reckless default)
  - routed      : a free local classifier picks local for easy, paid for hard

Cost is actual premium token usage x list price (local = 0). Quality is
exact-match on a deterministic "easy" set and a premium LLM judge (0/1) on a
"hard" set.

    TOGETHER_API_KEY=... python3 router_bench.py --out result.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/chat"
LOCAL = "qwen2.5:7b-instruct-q4_K_M"          # cheap tier: free, local
PREMIUM = "meta-llama/Llama-3.3-70B-Instruct-Turbo"  # premium tier: paid API
JUDGE = PREMIUM

# Together list price, USD per 1M tokens (Aug 2026). Local marginal cost = 0.
PRICE = {PREMIUM: 1.04, LOCAL: 0.0}

# ---- Easy set: deterministic, checkable answers -------------------------------
EASY = [
    ("Classify the sentiment as one word (positive/negative): 'I love this'.", "positive"),
    ("Extract only the email address from: contact me at bob@acme.io please.", "bob@acme.io"),
    ("What is 47 + 68? Reply with the number only.", "115"),
    ("What is the capital of France? One word.", "paris"),
    ("Convert to uppercase, reply with the word only: hello", "HELLO"),
    ("Which is larger, 0.9 or 0.85? Reply with the number.", "0.9"),
    ("Category for 'I was charged twice' as one word (billing/support/sales).", "billing"),
    ("Extract the date (YYYY-MM-DD) from: meeting on 2026-09-11 at noon.", "2026-09-11"),
    ("How many words in: the quick brown fox. Reply with the number.", "4"),
    ("What language is 'bonjour le monde'? One word.", "french"),
    ("Is 17 prime? Reply yes or no.", "yes"),
    ("First word of: Apple releases new chip. One word.", "apple"),
]

# ---- Hard set: judged 0/1 by the premium judge --------------------------------
HARD = [
    "Explain in 2-3 sentences why setting temperature to 0 does not make an LLM fully deterministic.",
    "Write a Python function fib(n) that returns the nth Fibonacci number iteratively (0-indexed, fib(0)=0).",
    "A farmer has 17 sheep. All but 9 die. How many sheep are left? Give the number and one line of reasoning.",
    "Give three bullet points on the trade-offs between deterministic and probabilistic steps in an automated workflow.",
    "Why might this loop never terminate: for i in range(len(x)): x.append(i) ? Explain in 2 sentences.",
    "Draft a two-sentence apology to a customer who was charged twice, professional British English.",
    "A room costs 30, guests get 5 back, the porter keeps 2, each guest gets 1 back. Explain in 2-3 sentences why 'where is the missing pound' is a trick question.",
    "Given a table orders(id, user_id, total), write a SQL query returning the top 3 users by total spend.",
    "A cost guard is meant to never block the fleet. Explain in 2 sentences why 'fail closed on error' is the wrong default for it.",
    "Explain the time complexity of binary search and why, in 2 sentences.",
    "Rewrite in plain English: 'we must utilise synergistic paradigms to action deliverables'.",
    "Two trains are 300 miles apart closing at 60 and 40 mph. How long until they meet? Give the number with units and one line of working.",
]


def ask_api(model, prompt, max_tokens=400):
    key = os.environ.get("TOGETHER_API_KEY") or sys.exit("TOGETHER_API_KEY not set")
    payload = {"model": model, "max_tokens": max_tokens, "temperature": 0.2,
               "messages": [{"role": "user", "content": prompt}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f); p = f.name
    try:
        for attempt in range(4):
            out = subprocess.run(
                ["curl", "-s", TOGETHER_URL, "-H", f"Authorization: Bearer {key}",
                 "-H", "Content-Type: application/json", "-d", f"@{p}"],
                capture_output=True, text=True, timeout=120).stdout
            try:
                d = json.loads(out)
            except json.JSONDecodeError:
                time.sleep(2 * (attempt + 1)); continue
            if "choices" in d:
                u = d.get("usage", {})
                return (d["choices"][0]["message"]["content"],
                        u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"api call failed: {out[:200]}")
    finally:
        os.unlink(p)


def ask_local(model, prompt, max_tokens=320):
    body = json.dumps({"model": model, "stream": False,
                       "messages": [{"role": "user", "content": prompt}],
                       "options": {"temperature": 0.2, "num_predict": max_tokens}}).encode()
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(OLLAMA_URL, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
            return (d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0))
        except Exception as e:  # transient CPU contention / timeout
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"local call failed after retries: {last}")


def cost_usd(model, pt, ct):
    return (pt + ct) / 1_000_000 * PRICE[model]


def norm(s):
    return re.sub(r"[^a-z0-9.]+", " ", s.lower()).strip()


def easy_correct(answer, expected):
    return norm(expected) in norm(answer)


def judge(prompt, answer):
    q = (f"You are grading an assistant answer. Task:\n{prompt}\n\nAnswer:\n{answer}\n\n"
         "Is the answer correct and genuinely useful? Reply with a single character: "
         "1 for yes, 0 for no.")
    out, _, _ = ask_api(JUDGE, q, max_tokens=3)
    return 1 if "1" in out else 0


def classify_difficulty(prompt):
    """Router brain runs on the free local model, so routing itself costs nothing."""
    q = ("Classify how hard this request is for a small model. Reply with one word, "
         "EASY or HARD. EASY = short factual, classification, extraction, arithmetic, "
         "formatting. HARD = multi-step reasoning, code, nuanced writing, tricky logic.\n\n"
         f"Request: {prompt}\nAnswer:")
    out, _, _ = ask_local(LOCAL, q, max_tokens=4)
    return "HARD" if "HARD" in out.upper() else "EASY"


def run():
    items = [{"prompt": p, "kind": "easy", "expected": e} for p, e in EASY] + \
            [{"prompt": p, "kind": "hard", "expected": None} for p in HARD]

    for it in items:
        ca, cpt, cct = ask_local(LOCAL, it["prompt"])
        pa, ppt, pct = ask_api(PREMIUM, it["prompt"])
        it["cheap"] = {"ans": ca, "cost": cost_usd(LOCAL, cpt, cct)}
        it["premium"] = {"ans": pa, "cost": cost_usd(PREMIUM, ppt, pct)}
        if it["kind"] == "easy":
            it["cheap"]["q"] = int(easy_correct(ca, it["expected"]))
            it["premium"]["q"] = int(easy_correct(pa, it["expected"]))
        else:
            it["cheap"]["q"] = judge(it["prompt"], ca)
            it["premium"]["q"] = judge(it["prompt"], pa)
        it["route"] = classify_difficulty(it["prompt"])
        print(f"  [{it['kind']:>4}] route={it['route']:<4} "
              f"local_q={it['cheap']['q']} api_q={it['premium']['q']} :: {it['prompt'][:46]}")

    n = len(items)
    all_cheap_cost = sum(it["cheap"]["cost"] for it in items)
    all_prem_cost = sum(it["premium"]["cost"] for it in items)
    all_cheap_q = sum(it["cheap"]["q"] for it in items)
    all_prem_q = sum(it["premium"]["q"] for it in items)

    routed_cost = routed_q = 0
    routed_local = 0
    for it in items:
        side = "cheap" if it["route"] == "EASY" else "premium"
        routed_cost += it[side]["cost"]
        routed_q += it[side]["q"]
        routed_local += 1 if side == "cheap" else 0

    def pct_saved(x):
        return round((all_prem_cost - x) / all_prem_cost * 100, 1) if all_prem_cost else 0.0

    summary = {
        "n": n, "local_model": LOCAL, "premium_model": PREMIUM,
        "premium_price_usd_per_mtok": PRICE[PREMIUM],
        "all_premium": {"cost": round(all_prem_cost, 6), "quality": all_prem_q},
        "all_cheap": {"cost": round(all_cheap_cost, 6), "quality": all_cheap_q,
                      "pct_saved": pct_saved(all_cheap_cost)},
        "routed": {"cost": round(routed_cost, 6), "quality": routed_q,
                   "pct_saved": pct_saved(routed_cost),
                   "sent_local": routed_local, "sent_premium": n - routed_local},
    }
    return {"summary": summary, "items": items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    print(f"local (free)   = {LOCAL}\npremium (paid) = {PREMIUM}\n")
    res = run()
    s = res["summary"]
    print(f"\nSUMMARY  (quality = correct/useful out of {s['n']})")
    for k in ("all_premium", "all_cheap", "routed"):
        row = s[k]
        extra = "" if k == "all_premium" else f"  saved {row['pct_saved']}%"
        print(f"  {k:<12} ${row['cost']:.5f}  quality {row['quality']}/{s['n']}{extra}")
    r = s["routed"]
    print(f"  routed sent {r['sent_local']} local / {r['sent_premium']} premium")
    if args.out:
        json.dump(res, open(args.out, "w"), indent=2)
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
