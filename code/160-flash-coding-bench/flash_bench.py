#!/usr/bin/env python3
"""
flash_bench.py — is a cheap frontier model good enough to be a coding subagent?

Google's Gemini 3.8 Flash lands at a fraction of frontier cost. This benchmark
tests whether it can actually do the boring, high-volume coding work you'd hand a
cheap tier, and what it costs, against two alternatives you'd realistically route
to instead: a strong paid open model (Llama 3.3 70B on Together) and a free local
model (qwen2.5:7b on Ollama).

Quality is graded DETERMINISTICALLY. Each task asks for a Python function with a
fixed signature; we extract the code and run it against hidden unit tests in a
subprocess. Pass means every assertion passed. No LLM judge, so the quality
number has no grader bias, which is the caveat that dogs most of these bench.

Cost is real token usage times list price. Prices are as-reported (see PRICES);
the harness prints tokens too, so you can plug your own contract rate.

Keys: GOOGLE_API_KEY and ANTHROPIC_API_KEY in
/home/workloft/larry-tier-routing/.env.tier-keys; TOGETHER_API_KEY in
/home/workloft/conexus/.env. Ollama on localhost:11434.

Usage: python3 flash_bench.py            # run all tiers, all tasks
       python3 flash_bench.py --tiers flash,local
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---- list prices, $ per 1M tokens (input, output). As-reported; edit to taste.
PRICES = {
    "flash": (0.75, 3.75),   # Gemini 3.8 Flash, per the 2026-09 launch reporting
    "paid":  (0.88, 0.88),   # Llama 3.3 70B Turbo on Together (single blended rate)
    "local": (0.0, 0.0),     # qwen2.5:7b on Ollama, self-hosted, zero marginal API cost
    "opus":  (5.0, 25.0),    # Claude Opus 4.8 list price
}

TIERS = {
    "flash": {"label": "Gemini 3.8 Flash", "provider": "google",   "model": "gemini-3.8-flash"},
    "paid":  {"label": "Llama 3.3 70B",    "provider": "together",  "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "local": {"label": "qwen2.5:7b (local)","provider": "ollama",   "model": "qwen2.5:7b-instruct-q4_K_M"},
    "opus":  {"label": "Claude Opus 4.8",  "provider": "anthropic", "model": "claude-opus-4-8"},
}


def load_env():
    env = {}
    for path in ("/home/workloft/larry-tier-routing/.env.tier-keys", "/home/workloft/conexus/.env"):
        try:
            for line in open(path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k, v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            pass
    return env


ENV = load_env()

# --------------------------------------------------------------------------- #
# Model callers. Each returns (text, in_tokens, out_tokens).
# --------------------------------------------------------------------------- #

def call_google(model, prompt):
    key = ENV["GOOGLE_API_KEY"]
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2048},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=180))
    cand = d["candidates"][0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    um = d.get("usageMetadata", {})
    return text, um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0)


def call_together(model, prompt):
    # Together sits behind Cloudflare that 1010s urllib; shell out to curl.
    key = ENV["TOGETHER_API_KEY"]
    payload = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    })
    out = subprocess.run(
        ["curl", "-s", "--max-time", "180", "https://api.together.xyz/v1/chat/completions",
         "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=200).stdout
    d = json.loads(out)
    text = d["choices"][0]["message"]["content"]
    u = d.get("usage", {})
    return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def call_anthropic(model, prompt):
    key = ENV["ANTHROPIC_API_KEY"]
    body = json.dumps({
        "model": model, "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=180))
    text = "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
    u = d.get("usage", {})
    return text, u.get("input_tokens", 0), u.get("output_tokens", 0)


def call_ollama(model, prompt):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "num_predict": 2048},
    }).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=300))
    return d.get("response", ""), d.get("prompt_eval_count", 0), d.get("eval_count", 0)


CALLERS = {"google": call_google, "together": call_together, "ollama": call_ollama,
           "anthropic": call_anthropic}

# --------------------------------------------------------------------------- #
# Tasks: (name, prompt, test_code). test_code asserts against the produced code.
# --------------------------------------------------------------------------- #

def task(name, sig, spec, tests):
    prompt = (
        f"Write a single Python function `{sig}`.\n{spec}\n"
        "Return ONLY the function definition in one Python code block. "
        "No explanation, no example usage, no prints."
    )
    return {"name": name, "prompt": prompt, "tests": tests}


TASKS = [
    task("duration_to_seconds", "duration_to_seconds(s: str) -> int",
         "Parse a duration string like '1h30m', '45s', '2h', '90m', '1h1m1s' into total seconds. "
         "Units are h, m, s. Any subset may appear, in that order.",
         "assert duration_to_seconds('1h30m')==5400\n"
         "assert duration_to_seconds('45s')==45\n"
         "assert duration_to_seconds('2h')==7200\n"
         "assert duration_to_seconds('90m')==5400\n"
         "assert duration_to_seconds('1h1m1s')==3661\n"),
    task("rle", "rle(s: str) -> str",
         "Run-length encode a string: 'aaabbc' -> 'a3b2c1'. Every run, even length 1, gets its count.",
         "assert rle('aaabbc')=='a3b2c1'\n"
         "assert rle('')==''\n"
         "assert rle('x')=='x1'\n"
         "assert rle('aabbaa')=='a2b2a2'\n"),
    task("is_balanced", "is_balanced(s: str) -> bool",
         "Return True if brackets (), [], {} in s are balanced and correctly nested; other chars ignored.",
         "assert is_balanced('(a[b]{c})') is True\n"
         "assert is_balanced('([)]') is False\n"
         "assert is_balanced('(((') is False\n"
         "assert is_balanced('') is True\n"
         "assert is_balanced('a+b') is True\n"),
    task("merge_intervals", "merge_intervals(ivs: list) -> list",
         "Merge overlapping [start,end] intervals; return sorted, merged list of lists.",
         "assert merge_intervals([[1,3],[2,6],[8,10]])==[[1,6],[8,10]]\n"
         "assert merge_intervals([[1,4],[4,5]])==[[1,5]]\n"
         "assert merge_intervals([])==[]\n"
         "assert merge_intervals([[5,6],[1,2]])==[[1,2],[5,6]]\n"),
    task("col_to_num", "col_to_num(col: str) -> int",
         "Spreadsheet column letters to number: A->1, Z->26, AA->27, AB->28.",
         "assert col_to_num('A')==1\n"
         "assert col_to_num('Z')==26\n"
         "assert col_to_num('AA')==27\n"
         "assert col_to_num('AB')==28\n"
         "assert col_to_num('ZZ')==702\n"),
    task("roman_to_int", "roman_to_int(s: str) -> int",
         "Convert an uppercase Roman numeral to an integer. Handle subtractive pairs (IV, IX, XL, ...).",
         "assert roman_to_int('IV')==4\n"
         "assert roman_to_int('MCMXCIV')==1994\n"
         "assert roman_to_int('III')==3\n"
         "assert roman_to_int('LVIII')==58\n"),
    task("flatten_keys", "flatten_keys(d: dict) -> dict",
         "Flatten a nested dict into dotted keys: {'a':{'b':1},'c':2} -> {'a.b':1,'c':2}. Recurse arbitrarily deep.",
         "assert flatten_keys({'a':{'b':1},'c':2})=={'a.b':1,'c':2}\n"
         "assert flatten_keys({'a':{'b':{'c':3}}})=={'a.b.c':3}\n"
         "assert flatten_keys({})=={}\n"
         "assert flatten_keys({'x':1})=={'x':1}\n"),
    task("top_k_frequent", "top_k_frequent(nums: list, k: int) -> list",
         "Return the k most frequent ints, most frequent first. Ties broken by first appearance in nums.",
         "assert top_k_frequent([1,1,1,2,2,3],2)==[1,2]\n"
         "assert top_k_frequent([4,4,5,5,6],2)==[4,5]\n"
         "assert top_k_frequent([7],1)==[7]\n"),
]

HARNESS = """
import sys
{code}
try:
{tests}
except Exception as e:
    print("FAIL:", type(e).__name__, e); sys.exit(1)
print("PASS")
"""


def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def grade(code, tests):
    indented = "\n".join("    " + ln for ln in tests.splitlines())
    prog = HARNESS.format(code=code, tests=indented)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(prog)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        Path(path).unlink(missing_ok=True)


def cost(tier, tin, tout):
    pin, pout = PRICES[tier]
    return (tin * pin + tout * pout) / 1_000_000


def run(tiers):
    results = {}
    for tkey in tiers:
        spec = TIERS[tkey]
        caller = CALLERS[spec["provider"]]
        passed = tin = tout = 0
        secs = 0.0
        per = []
        print(f"\n=== {spec['label']} ({spec['model']}) ===", flush=True)
        for t in TASKS:
            t0 = time.time()
            # Retry transient call errors (rate limits, network) so an infra blip
            # is not misreported as the model getting the task wrong. A graded-wrong
            # answer is a real FAIL; a call that never returned is retried.
            a = b = 0
            ok = False
            for attempt in range(3):
                try:
                    text, a, b = caller(spec["model"], t["prompt"])
                    ok = grade(extract_code(text), t["tests"])
                    break
                except Exception as e:
                    text = f"<error: {e}>"
                    if attempt < 2:
                        time.sleep(2)
            dt = time.time() - t0
            secs += dt
            tin += a
            tout += b
            passed += int(ok)
            per.append({"task": t["name"], "pass": ok, "in": a, "out": b, "s": round(dt, 1)})
            print(f"  [{'PASS' if ok else 'FAIL'}] {t['name']:<20} {a:>5}+{b:<5}tok {dt:>5.1f}s", flush=True)
        results[tkey] = {
            "label": spec["label"], "model": spec["model"],
            "passed": passed, "total": len(TASKS),
            "in_tokens": tin, "out_tokens": tout,
            "cost_usd": round(cost(tkey, tin, tout), 6),
            "seconds": round(secs, 1), "per_task": per,
        }
    return results


def report(results):
    print("\n" + "=" * 68)
    print(f"{'tier':<22}{'pass':>7}{'cost $':>12}{'tokens':>12}{'time':>8}")
    print("-" * 68)
    for r in results.values():
        print(f"{r['label']:<22}{r['passed']}/{r['total']:<5}"
              f"{r['cost_usd']:>12.6f}{r['in_tokens']+r['out_tokens']:>12}{r['seconds']:>7.0f}s")
    print("=" * 68)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="flash,paid,local",
                    help="comma list of: flash, paid, local")
    ap.add_argument("--out", default="result.json")
    args = ap.parse_args()
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip() in TIERS]
    res = run(tiers)
    report(res)
    Path(args.out).write_text(json.dumps(res, indent=2))
    print(f"\nwrote {args.out}")
