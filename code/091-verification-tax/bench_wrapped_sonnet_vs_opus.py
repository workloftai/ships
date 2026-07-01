#!/usr/bin/env python3
"""Wrapped Sonnet 5 vs bare Opus 4.8: does a verification loop buy back accuracy
cheaply enough to beat the stronger single-pass model on cost-per-VERIFIED-correct?

Context: on 6 hard exact-integer reasoning tasks, bare Opus 4.8 scored 6/6 and bare
Sonnet 5 scored 5/6 (an off-by-2 counting slip), but Sonnet was ~27% cheaper per
correct answer. Question: can a verification wrapper rescue Sonnet's miss without
spending the cost edge away?

Perplexity Research sharpened the design. The findings we act on here:
  1. A same-model verifier is a confidence amplifier, not an error filter
     (64.5% self-correction blind-spot rate across 14 models). So the verifier is a
     DIFFERENT family: Claude Haiku 4.5 judges Sonnet, and it sees only the question
     and the stated answer, NEVER Sonnet's reasoning chain (which would anchor it).
  2. Appending the token "Wait" before a second pass is a near-free correction lift.
     Every retry prompt starts with it.
  3. Hard 2-retry cap, enforced by the orchestrator, not the model.
  4. A code-execution gate is the standout verifier FOR TASKS THAT ARE CODEABLE.
     Our 6 tasks all are, so we report it SEPARATELY and honestly: it flatters the
     gate. The transferable result for genuine reasoning is the Haiku-verifier column.

Four columns, same 6 tasks, exact self-graded answers:
  - bare Opus 4.8            (baseline strong single-pass)
  - bare Sonnet 5           (baseline cheap single-pass)
  - wrapped Sonnet 5        (Wait-retry + Haiku heterogeneous verifier, 2-retry cap)
  - wrapped Sonnet 5 + code (adds a Python execution gate; codeable tasks only)

Model IDs verified live 2026-07-01: claude-sonnet-5, claude-opus-4-8,
claude-haiku-4-5-20251001.
"""
import json
import re
import subprocess
import tempfile
import time
import os
import urllib.request as urlreq
import urllib.error as urlerr

def load_key():
    # Public mirror: read the key straight from the environment.
    #   export ANTHROPIC_API_KEY=sk-ant-...
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        raise SystemExit("set ANTHROPIC_API_KEY in your environment")
    return key.strip()


AKEY = load_key()
# ($/M input, $/M output). Sonnet/Opus verified live 2026-07-01 in the prior bench.
PRICING = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
MAX_TOKENS = 24000
MAX_RETRIES = 2  # hard cap, orchestrator-enforced


# ---- reference answers, brute-forced here so grading is exact & independent ----
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
    s = sieve(1000)
    return sum(1 for p in range(2, 501) if s[p] and s[p + 2])


def ref_coin_change():
    coins = [1, 2, 5, 10, 20, 50]
    ways = [0] * 101
    ways[0] = 1
    for c in coins:
        for amt in range(c, 101):
            ways[amt] += ways[amt - c]
    return ways[100]


def ref_collatz():
    best, best_n = 0, 0
    cache = {1: 0}
    for start in range(1, 1001):
        n, steps, seen = start, 0, []
        while n not in cache:
            seen.append(n)
            n = n // 2 if n % 2 == 0 else 3 * n + 1
            steps += 1
        total = steps + cache[n]
        for i, v in enumerate(seen):
            cache[v] = total - i
        if cache[start] > best:
            best, best_n = cache[start], start
    return best_n


def ref_taxicab():
    seen = {}
    for a in range(1, 40):
        for b in range(a, 40):
            s = a ** 3 + b ** 3
            seen.setdefault(s, 0)
            seen[s] += 1
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


def call(model, messages, rich=True):
    # Try rich (adaptive thinking + high effort); on a 400 fall back to a bare call.
    attempts = [True, False] if rich else [False]
    resp = None
    for attempt_rich in attempts:
        body = {"model": model, "max_tokens": MAX_TOKENS, "messages": messages}
        if attempt_rich:
            body["thinking"] = {"type": "adaptive"}
            body["output_config"] = {"effort": "high"}
        req = urlreq.Request("https://api.anthropic.com/v1/messages",
                             data=json.dumps(body).encode(),
                             headers={"x-api-key": AKEY, "anthropic-version": "2023-06-01",
                                      "content-type": "application/json"})
        try:
            resp = json.loads(urlreq.urlopen(req, timeout=900).read())
            break
        except urlerr.HTTPError as e:
            if e.code == 400 and attempt_rich:
                continue
            raise
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    u = resp.get("usage", {})
    return {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
            "text": text.strip(), "stop": resp.get("stop_reason")}


def last_int(text):
    nums = re.findall(r"-?\d[\d,]*", text or "")
    return nums[-1].replace(",", "") if nums else None


def graded(text, answer):
    return last_int(text) == answer


def cost(inp, out, price):
    return inp / 1e6 * price[0] + out / 1e6 * price[1]


# ------------------------- baselines (single pass) -------------------------
def run_bare(model):
    inp = out = correct = 0
    rows = []
    for i, (task, ans) in enumerate(TASKS):
        try:
            r = call(model, [{"role": "user", "content": task}], rich=True)
        except Exception as e:
            rows.append({"t": i, "error": str(e)[:150]})
            continue
        ok = graded(r["text"], ans)
        correct += int(ok)
        inp += r["in"]; out += r["out"]
        rows.append({"t": i, "in": r["in"], "out": r["out"], "got": last_int(r["text"]),
                     "exp": ans, "ok": ok})
        print(f"  [{model}] task{i}: {'OK ' if ok else 'MISS'} "
              f"got={last_int(r['text'])} exp={ans} in={r['in']} out={r['out']}", flush=True)
        time.sleep(1)
    c = cost(inp, out, PRICING[model])
    return {"model": model, "in": inp, "out": out, "correct": correct,
            "of": len(TASKS), "cost_usd": c,
            "cost_per_correct": c / correct if correct else None, "rows": rows}


# ------------------------- heterogeneous verifier -------------------------
VERIFIER = "claude-haiku-4-5-20251001"


def haiku_verify(task, stated):
    """Different-family verifier. Sees ONLY the question and the stated answer,
    never the generator's chain. Independently derives; returns (agrees, its_int, usage)."""
    prompt = (f"You are an independent checker. Solve this problem yourself from scratch, "
              f"then judge the proposed answer.\n\nPROBLEM:\n{task}\n\n"
              f"PROPOSED ANSWER: {stated}\n\n"
              f"Work it out independently. End your reply with a line exactly of the form "
              f"'VERDICT: <your integer>'.")
    r = call(VERIFIER, [{"role": "user", "content": prompt}], rich=True)
    m = re.search(r"VERDICT:\s*(-?\d[\d,]*)", r["text"])
    vint = m.group(1).replace(",", "") if m else last_int(r["text"])
    return (vint == stated, vint, r["in"], r["out"])


def run_wrapped(use_code_gate):
    """Wrapped Sonnet 5: gen -> Wait-retry -> Haiku verify -> (bounded) re-derive.
    Optional code-execution gate (codeable tasks only)."""
    model = "claude-sonnet-5"
    inp = out = correct = 0
    vin = vout = 0
    rows = []
    for i, (task, ans) in enumerate(TASKS):
        msgs = [{"role": "user", "content": task}]
        try:
            r1 = call(model, msgs, rich=True)
        except Exception as e:
            rows.append({"t": i, "error": str(e)[:150]}); continue
        inp += r1["in"]; out += r1["out"]
        stated = last_int(r1["text"])
        last_asst = r1["text"]
        retries = 0
        trace = ["gen"]

        # Round 1: Wait-token self re-examination (near-free correction lift)
        if retries < MAX_RETRIES:
            msgs = msgs + [{"role": "assistant", "content": last_asst},
                          {"role": "user", "content": "Wait. Re-examine that carefully for "
                           "off-by-one and counting mistakes, then give only the final integer."}]
            try:
                r2 = call(model, msgs, rich=True)
                inp += r2["in"]; out += r2["out"]
                stated = last_int(r2["text"]) or stated
                last_asst = r2["text"]
                retries += 1; trace.append("wait")
            except Exception:
                pass

        # Code-execution gate (deterministic; codeable tasks only)
        gate_int = None
        if use_code_gate:
            gate_int, gin, gout = code_gate(task)
            inp += gin; out += gout
            if gate_int is not None:
                trace.append("code")
                stated = gate_int  # deterministic answer wins when the gate runs

        # Round 2: heterogeneous verifier (Haiku, question+answer only)
        if not use_code_gate or gate_int is None:
            agrees, vint, hi, ho = haiku_verify(task, stated)
            vin += hi; vout += ho
            trace.append("verify")
            if not agrees and retries < MAX_RETRIES:
                msgs = msgs + [{"role": "assistant", "content": last_asst},
                              {"role": "user", "content": f"Wait. An independent check derived {vint}, "
                               f"which disagrees with your answer. Re-derive from scratch and give only "
                               f"the final integer."}]
                try:
                    r3 = call(model, msgs, rich=True)
                    inp += r3["in"]; out += r3["out"]
                    stated = last_int(r3["text"]) or stated
                    last_asst = r3["text"]
                    retries += 1; trace.append("rederive")
                except Exception:
                    pass

        ok = (stated == ans)
        correct += int(ok)
        rows.append({"t": i, "final": stated, "exp": ans, "ok": ok,
                     "retries": retries, "trace": "+".join(trace)})
        print(f"  [wrapped{'+code' if use_code_gate else ''}] task{i}: "
              f"{'OK ' if ok else 'MISS'} final={stated} exp={ans} trace={'+'.join(trace)}", flush=True)
        time.sleep(1)

    gen_cost = cost(inp, out, PRICING[model])
    ver_cost = cost(vin, vout, PRICING[VERIFIER])
    total = gen_cost + ver_cost
    return {"model": f"wrapped-sonnet-5{'+code' if use_code_gate else ''}",
            "in": inp, "out": out, "verifier_in": vin, "verifier_out": vout,
            "correct": correct, "of": len(TASKS),
            "gen_cost_usd": gen_cost, "verifier_cost_usd": ver_cost, "cost_usd": total,
            "cost_per_correct": total / correct if correct else None, "rows": rows}


BANNED = ("import os", "import sys", "import subprocess", "import socket", "open(",
          "__import__", "eval(", "exec(", "input(", "urllib", "requests", "shutil",
          "pathlib", "system(")


def code_gate(task):
    """Ask Sonnet for a self-contained Python snippet that prints the integer, then
    execute it in an isolated subprocess with a timeout. Returns (int|None, in, out)."""
    prompt = (f"Write a short self-contained Python 3 program that computes the answer to "
              f"this problem and prints ONLY the integer, nothing else. No input, no imports "
              f"except 'math'. Output just the code, no markdown fences.\n\nPROBLEM:\n{task}")
    r = call("claude-sonnet-5", [{"role": "user", "content": prompt}], rich=False)
    code = r["text"]
    if "```" in code:
        code = re.sub(r"```(?:python)?", "", code).strip()
    low = code.lower()
    if any(b in low for b in BANNED):
        return None, r["in"], r["out"]
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code); path = f.name
        p = subprocess.run(["python3", "-I", path], capture_output=True, text=True,
                           timeout=20, env={"PATH": "/usr/bin:/bin"})
        os.unlink(path)
        val = last_int(p.stdout)
        return val, r["in"], r["out"]
    except Exception:
        return None, r["in"], r["out"]


def main():
    print("reference answers:", [a for _, a in TASKS], flush=True)
    results = []

    print("\n=== bare claude-opus-4-8 ===", flush=True)
    results.append(run_bare("claude-opus-4-8"))
    print("\n=== bare claude-sonnet-5 ===", flush=True)
    results.append(run_bare("claude-sonnet-5"))
    print("\n=== wrapped sonnet-5 (Wait + Haiku verifier) ===", flush=True)
    results.append(run_wrapped(use_code_gate=False))
    print("\n=== wrapped sonnet-5 + code gate ===", flush=True)
    results.append(run_wrapped(use_code_gate=True))

    json.dump(results, open("/home/workloft/ruby/cost_wrapped_sonnet_vs_opus.json", "w"), indent=2)

    print("\n================ WRAPPED SUMMARY ================", flush=True)
    print(f"{'variant':28s} | correct | cost/correct | total cost", flush=True)
    for res in results:
        cpc = f"${res['cost_per_correct']:.5f}" if res["cost_per_correct"] else "n/a"
        print(f"{res['model']:28s} | {res['correct']}/{res['of']}     | {cpc:>11s} "
              f"| ${res['cost_usd']:.5f}", flush=True)
    print("\nwrote cost_wrapped_sonnet_vs_opus.json", flush=True)


if __name__ == "__main__":
    main()
