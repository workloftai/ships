#!/usr/bin/env python3
"""
bench_reasoning_swap.py - measure the reasoning overhead a model picks up when
a provider turns a cheap "flash" model into a reasoning-by-default model under
the same id.

Runs a small mechanical suite (classify / extract, the day job of a cheap tier)
against two OpenRouter models at temperature 0 and reports, per model:
  - accuracy on exact-ish match
  - null answers (content=None: reasoning ate the token budget)
  - total reasoning tokens burned across the suite
  - cost per 1,000 tasks
  - average latency

The point it makes: with a generous max_tokens the reasoning model still scores
well and stays cheap, so "the upgrade ruined it" is false. But it fires reasoning
unpredictably on trivial tasks and runs slower, and under the tight max_tokens a
cheap mechanical tier actually uses, that intermittency becomes a null reply.

Requires: OPENROUTER_API_KEY in the environment. Stdlib only.
"""
import json, os, time, urllib.request, urllib.error

KEY = os.environ.get("OPENROUTER_API_KEY")
if not KEY:
    raise SystemExit("set OPENROUTER_API_KEY")

TASKS = [
    ("Classify sentiment as one word (positive/negative/neutral): 'The delivery was late and stone cold.'", "negative"),
    ("Is this spam? Answer spam or ham only: 'You WON a FREE prize!!! Click now to claim'", "spam"),
    ("Priority (high/medium/low), one word: 'Production server down, all customers affected.'", "high"),
    ("Extract the email address only: 'please contact jane.doe@acme.co.uk about the order'", "jane.doe@acme.co.uk"),
    ("Extract the UK postcode only: 'Our office is at 221B Baker Street, London NW1 6XE'", "NW1 6XE"),
    ("Extract the total amount only: 'Total due is 1240.50 including VAT'", "1240.50"),
    ("Convert to ISO date (YYYY-MM-DD), output date only: '3rd July 2026'", "2026-07-03"),
    ("Answer yes or no only: is 17 a prime number?", "yes"),
    ("How many words are in this list, number only: 'red green blue yellow'", "4"),
    ("Extract the full name including title only: 'Dr Alan Grant will attend the dig.'", "dr alan grant"),
]

# Swap in whatever pair you want to compare. Defaults: a reasoning "flash" model
# vs a non-reasoning sibling.
MODELS = [
    ("v4-flash (reasoning)", "deepseek/deepseek-v4-flash"),
    ("v3 (no reasoning)", "deepseek/deepseek-chat-v3-0324"),
]

# reasoning=None -> provider default; {"enabled": False} -> force reasoning off.
def call(model_id, prompt, max_tokens, reasoning=None):
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Answer with ONLY the requested value. No explanation."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if reasoning is not None:
        payload["reasoning"] = reasoning
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    dt = time.time() - t0
    msg = data["choices"][0]["message"]
    usage = data.get("usage", {})
    rt = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
    return (msg.get("content") or ""), rt, usage.get("cost", 0.0), dt


def run(max_tokens=512, reasoning=None):
    for label, mid in MODELS:
        hits = nulls = tot_rt = 0
        tot_cost = tot_dt = 0.0
        for prompt, expected in TASKS:
            content, rt, cost, dt = call(mid, prompt, max_tokens, reasoning)
            ok = expected.lower() in content.lower()
            hits += ok
            nulls += (content == "")
            tot_rt += rt
            tot_cost += cost
            tot_dt += dt
            print(f"  [{'PASS' if ok else 'FAIL'}] {expected!r:22} -> {content[:40]!r:42} rt={rt:>4} ${cost:.6f}")
        n = len(TASKS)
        print(f"== {label}: acc={hits}/{n} nulls={nulls} reason_tok={tot_rt} "
              f"cost/1k=${tot_cost/n*1000:.3f} lat={tot_dt/n:.2f}s\n")


if __name__ == "__main__":
    print("max_tokens=512 (headroom): measure reasoning overhead")
    run(max_tokens=512)
    print("max_tokens=20 (tight, the mechanical-tier reality): watch for nulls")
    run(max_tokens=20)
    print("max_tokens=20 + reasoning disabled: the fix")
    run(max_tokens=20, reasoning={"enabled": False})
