#!/usr/bin/env python3
"""
A/B two models on a code/reasoning suite, priced on real token counts.

Built to answer one question honestly: when a new model claims "cheaper AND
better", is it? Here it's Gemini 3.7 Flash ($0.75/$3.75 per M) vs Gemini 2.5 Pro
($1.25/$10.00) on twelve tasks with a single checkable answer each. Real Google
API calls, temperature 0, a fixed token budget for both. It captures the hidden
*thinking* tokens too, because a heavy reasoner's real cost is the price times
how many tokens it decides to think for — and on a bounded budget it can spend
the lot on thinking and return nothing.

    GOOGLE_API_KEY=... python3 bench.py

Swap the MODELS list and prices for any two Gemini models. The pattern (fixed
budget, grade the final value, bill thinking tokens as output) ports to any
provider that reports token usage.
"""
import json, os, time, urllib.request, urllib.error

KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
if not KEY:
    raise SystemExit("set GOOGLE_API_KEY")

# (prompt, expected substring in the answer, case-insensitive)
TASKS = [
    ("Write fib(n) for the nth Fibonacci number (fib(1)=1, fib(2)=1) and give fib(20). End with 'ANSWER: <number>'.", "6765"),
    ("A train covers 60 km in 45 minutes. What is its speed in km/h? End with 'ANSWER: <number>'.", "80"),
    ("How many times does the letter r appear in 'strawberry raspberry'? End with 'ANSWER: <number>'.", "6"),
    ("What is the sum of the first 50 positive even numbers? End with 'ANSWER: <number>'.", "2550"),
    ("If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops necessarily Lazzies? End with 'ANSWER: yes' or 'ANSWER: no'.", "yes"),
    ("What is 17 * 23? End with 'ANSWER: <number>'.", "391"),
    ("Given def f(x): return x*x - 1, what does f(5) return? End with 'ANSWER: <number>'.", "24"),
    ("Convert binary 1011 to decimal. End with 'ANSWER: <number>'.", "11"),
    ("What is the next number in the sequence 2, 6, 12, 20, 30, ? End with 'ANSWER: <number>'.", "42"),
    ("How many days are in January plus February 2026 (2026 is not a leap year)? End with 'ANSWER: <number>'.", "59"),
    ("For the list [3,1,4,1,5,9,2,6], what is the sum of the distinct values? End with 'ANSWER: <number>'.", "30"),
    ("How many 1-bits are in the binary representation of 2024? End with 'ANSWER: <number>'.", "7"),
]

# (label, api_id, price_in_per_m, price_out_per_m)
MODELS = [
    ("gemini-3.7-flash", "gemini-3.7-flash", 0.75, 3.75),
    ("gemini-2.5-pro",   "gemini-2.5-pro",   1.25, 10.00),
]


def call(api_id, prompt, max_tokens=2048):
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{api_id}:generateContent?key={KEY}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    dt = time.time() - t0
    text = ""
    for c in data.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            text += p.get("text", "")
    u = data.get("usageMetadata", {})
    return (text.strip(), u.get("promptTokenCount", 0),
            u.get("candidatesTokenCount", 0), u.get("thoughtsTokenCount", 0), dt)


def score(text, expected):
    return expected.lower() in text.lower()


results = {}
for label, api_id, p_in, p_out in MODELS:
    print(f"\n=== {label}  ${p_in}/${p_out} per M ===")
    hits = tot_in = tot_out = tot_think = 0
    tot_cost = tot_dt = 0.0
    for prompt, expected in TASKS:
        try:
            text, in_tok, out_tok, think_tok, dt = call(api_id, prompt)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read()[:200]!r}")
            continue
        ok = score(text, expected)
        billed_out = out_tok + think_tok
        cost = (p_in * in_tok + p_out * billed_out) / 1_000_000
        hits += ok
        tot_in += in_tok; tot_out += out_tok; tot_think += think_tok
        tot_cost += cost; tot_dt += dt
        print(f"  [{'PASS' if ok else 'FAIL'}] exp={expected:>6}  "
              f"in={in_tok:>4} out={out_tok:>4} think={think_tok:>4} cost=${cost:.6f}")
    n = len(TASKS)
    results[label] = {
        "accuracy": hits / n, "hits": hits, "n": n,
        "total_thinking_tokens": tot_think,
        "cost_per_1k_tasks_usd": round(tot_cost / n * 1000, 4),
        "avg_latency_s": round(tot_dt / n, 2),
    }
    print(f"  -> acc={hits}/{n}  think_tok={tot_think}  "
          f"cost/1k=${tot_cost/n*1000:.3f}  avg_lat={tot_dt/n:.2f}s")

a, b = results[MODELS[0][0]], results[MODELS[1][0]]
print("\n=== HEAD TO HEAD ===")
print(f"  accuracy:  {a['hits']}/{a['n']}  vs  {b['hits']}/{b['n']}")
print(f"  cost/1k:   ${a['cost_per_1k_tasks_usd']}  vs  ${b['cost_per_1k_tasks_usd']}")
if b["cost_per_1k_tasks_usd"]:
    saving = 100 * (1 - a["cost_per_1k_tasks_usd"] / b["cost_per_1k_tasks_usd"])
    print(f"  {MODELS[0][0]} is {saving:.0f}% {'cheaper' if saving>0 else 'dearer'} per task")
print(f"  latency:   {a['avg_latency_s']}s  vs  {b['avg_latency_s']}s")
