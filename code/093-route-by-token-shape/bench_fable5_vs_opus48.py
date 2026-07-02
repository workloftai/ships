#!/usr/bin/env python3
"""Fable 5 vs Opus 4.8 on hard reasoning tasks, direct on the Anthropic API.

Same harness as bench_hard_sonnet5_vs_opus48.py: the model gets NO code
execution and must reason to an exact integer; every reference answer is
brute-forced by THIS script so grading is exact.

Three configs, because Fable's effort knob moves the bill more than model
choice:
  - claude-opus-4-8  (adaptive thinking, effort high)  — the incumbent
  - claude-fable-5   (effort medium)                   — recommended default
  - claude-fable-5   (effort high)                     — the expensive end

Key metric: cost per CORRECT task at list prices (Fable $10/$50, Opus $5/$25).
"""
import json
import re
import time
import urllib.request as urlreq
import urllib.error as urlerr

KEYFILE = "/home/workloft/larry-tier-routing/.env.tier-keys"


def load_key():
    for line in open(KEYFILE):
        line = line.strip()
        if line.startswith(("ANTHROPIC_API_KEY=", "ANTHROPIC_AUTH_TOKEN=")):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no Anthropic key")


AKEY = load_key()
PRICING = {"claude-fable-5": (10.0, 50.0), "claude-opus-4-8": (5.0, 25.0)}
MAX_TOKENS = 24000


# ---- reference answers, brute-forced here so grading is exact ----
def ref_pairs_pythag():
    import math
    c = 0
    for a in range(1, 61):
        for b in range(1, 61):
            r = math.isqrt(a * a + b * b)
            if r * r == a * a + b * b:
                c += 1
    return c


def ref_palindromes():
    return sum(1 for n in range(1, 100001) if str(n) == str(n)[::-1])


def ref_twin_lowers():
    def sieve(n):
        s = [True] * (n + 1)
        s[0] = s[1] = False
        for i in range(2, int(n ** 0.5) + 1):
            if s[i]:
                for j in range(i * i, n + 1, i):
                    s[j] = False
        return s

    s = sieve(502)
    return sum(1 for p in range(2, 501) if s[p] and s[p + 2])


def ref_coin_change():
    coins = [1, 2, 5, 10, 20, 50]
    ways = [1] + [0] * 100
    for c in coins:
        for v in range(c, 101):
            ways[v] += ways[v - c]
    return ways[100]


def ref_collatz():
    best_n, best_len = 1, 1
    for n in range(1, 1001):
        m, ln = n, 1
        while m != 1:
            m = m // 2 if m % 2 == 0 else 3 * m + 1
            ln += 1
        if ln > best_len:
            best_n, best_len = n, ln
    return best_n


def ref_taxicab():
    seen = {}
    for a in range(1, 50):
        for b in range(a, 50):
            s = a ** 3 + b ** 3
            seen[s] = seen.get(s, 0) + 1
    return min(k for k, v in seen.items() if v >= 2)


TASKS = [
    ("Count the ordered pairs (a, b) of integers with 1 <= a <= 60 and 1 <= b <= 60 "
     "such that a^2 + b^2 is a perfect square. Reply with only the integer.",
     str(ref_pairs_pythag())),
    ("How many integers from 1 to 100000 inclusive are palindromes in base 10 "
     "(read the same forwards and backwards)? Reply with only the integer.",
     str(ref_palindromes())),
    ("How many primes p with p <= 500 are such that p + 2 is also prime? "
     "Reply with only the integer.", str(ref_twin_lowers())),
    ("In how many distinct ways can you make exactly 100 pence using any number of "
     "coins of denominations 1, 2, 5, 10, 20 and 50 pence (order does not matter)? "
     "Reply with only the integer.", str(ref_coin_change())),
    ("Among all starting integers from 1 to 1000, which one produces the longest "
     "Collatz sequence before reaching 1 (n -> n/2 if even, 3n+1 if odd)? "
     "Reply with only that starting integer.", str(ref_collatz())),
    ("What is the smallest positive integer expressible as the sum of two positive "
     "cubes in two different ways? Reply with only the integer.", str(ref_taxicab())),
]


def call(model, task, rich, effort):
    body = {"model": model, "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": task}]}
    if rich:
        body["thinking"] = {"type": "adaptive"}
        body["output_config"] = {"effort": effort}
    req = urlreq.Request("https://api.anthropic.com/v1/messages",
                         data=json.dumps(body).encode(),
                         headers={"x-api-key": AKEY, "anthropic-version": "2023-06-01",
                                  "content-type": "application/json"})
    resp = json.loads(urlreq.urlopen(req, timeout=900).read())
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    u = resp.get("usage", {})
    return {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
            "text": text.strip(), "stop": resp.get("stop_reason"),
            "model_used": resp.get("model", model)}


def graded(text, answer):
    nums = re.findall(r"-?\d[\d,]*", text)
    if not nums:
        return False
    return nums[-1].replace(",", "") == answer


def run_config(model, effort):
    inp = out = correct = 0
    mode = "rich"
    rows = []
    fallbacks = 0
    for i, (task, ans) in enumerate(TASKS):
        r = None
        for attempt_rich in (True, False):
            try:
                r = call(model, task, attempt_rich, effort)
                mode = "rich" if attempt_rich else "bare"
                break
            except urlerr.HTTPError as e:
                if e.code == 400 and attempt_rich:
                    continue
                rows.append({"t": i, "error": f"{e.code} {e.read().decode()[:150]}"})
                r = None
                break
            except Exception as e:
                rows.append({"t": i, "error": str(e)[:150]})
                r = None
                break
        if not r:
            continue
        # Fable's safety classifiers can silently reroute to Opus; count it.
        if model not in r["model_used"]:
            fallbacks += 1
        ok = graded(r["text"], ans)
        correct += int(ok)
        inp += r["in"]
        out += r["out"]
        rows.append({"t": i, "in": r["in"], "out": r["out"], "got": r["text"][-20:],
                     "exp": ans, "ok": ok, "stop": r["stop"], "model_used": r["model_used"]})
        print(f"  [{model}/{effort}] task{i}: {'OK ' if ok else 'MISS'} "
              f"got=...{r['text'][-12:]!r} exp={ans} in={r['in']} out={r['out']} "
              f"served_by={r['model_used']}", flush=True)
        time.sleep(1)
    return {"model": model, "effort": effort, "mode": mode, "in": inp, "out": out,
            "correct": correct, "of": len(TASKS), "fallbacks": fallbacks, "rows": rows}


def cost(inp, out, price):
    return inp / 1e6 * price[0] + out / 1e6 * price[1]


def main():
    print("reference answers:", [a for _, a in TASKS], flush=True)
    results = []
    for model, effort in (("claude-opus-4-8", "high"),
                          ("claude-fable-5", "medium"),
                          ("claude-fable-5", "high")):
        print(f"\n=== {model} (effort={effort}) ===", flush=True)
        res = run_config(model, effort)
        res["cost_usd"] = cost(res["in"], res["out"], PRICING[model])
        res["cost_per_correct"] = res["cost_usd"] / res["correct"] if res["correct"] else None
        results.append(res)
        cpc = f"${res['cost_per_correct']:.5f}" if res["cost_per_correct"] else "n/a"
        print(f"  totals: {res['correct']}/{res['of']} correct | in={res['in']} out={res['out']} "
              f"| cost=${res['cost_usd']:.5f} | per-correct={cpc} | mode={res['mode']} "
              f"| opus_fallbacks={res['fallbacks']}", flush=True)

    json.dump(results, open("/home/workloft/ruby/cost_fable5_vs_opus48.json", "w"), indent=2)

    print("\n================ FABLE vs OPUS SUMMARY ================", flush=True)
    for res in results:
        cpc = f"${res['cost_per_correct']:.5f}/correct" if res["cost_per_correct"] else "n/a"
        print(f"{res['model']:18s} effort={res['effort']:6s} | {res['correct']}/{res['of']} "
              f"| in {res['in']:>6} out {res['out']:>7} | ${res['cost_usd']:.5f} | {cpc} "
              f"| fallbacks={res['fallbacks']}", flush=True)
    print("\nwrote cost_fable5_vs_opus48.json", flush=True)


if __name__ == "__main__":
    main()
