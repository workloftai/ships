#!/usr/bin/env python3
"""
Astra vs Opus cost-per-solved-task eval.
Reproducible harness: same golden set, same prompts, deterministic grading.
Each model called via OpenRouter; cost taken from OpenRouter's own usage.cost.

Usage:
  python3 run_eval.py <model_id> <api_key_env_var> [label]
e.g.
  python3 run_eval.py openai/gpt-6-astra OPENROUTER_TIER3_KEY astra
  python3 run_eval.py anthropic/claude-opus-4.8 OPENROUTER_TIER3_KEY opus48
Results appended to results.jsonl and a per-run summary printed + written to summary_<label>.json
"""
import json, os, re, sys, time, subprocess, tempfile, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.environ.get("GOLDEN_SET") or os.path.join(HERE, "golden_set.json")
URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# List price per token (USD), used to compute cost for direct-Anthropic calls.
# Matches what OpenRouter passes through, so cost is comparable across providers.
PRICE = {
    "claude-opus-4-8": (5e-6, 25e-6),
    "claude-opus-4.8": (5e-6, 25e-6),
    "claude-opus-5":   (5e-6, 25e-6),
}


def call_anthropic(model, key, prompt, max_tokens=1200):
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ANTHROPIC_URL, data=body, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        d = json.load(e)
    dt = time.time() - t0
    if "content" not in d:
        return {"error": d.get("error", d), "latency": dt}
    u = d.get("usage", {})
    pin, pout = PRICE.get(model, (5e-6, 25e-6))
    it, ot = u.get("input_tokens", 0), u.get("output_tokens", 0)
    return {
        "content": "".join(b.get("text", "") for b in d["content"]),
        "prompt_tokens": it,
        "completion_tokens": ot,
        "cost": it * pin + ot * pout,
        "latency": dt,
        "provider": "anthropic-direct",
    }


def call(model, key, prompt, max_tokens=1200):
    # bare claude-* model id (no slash) => call Anthropic directly
    if "/" not in model:
        return call_anthropic(model, key, prompt, max_tokens)
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        d = json.load(e)
    dt = time.time() - t0
    if "choices" not in d:
        return {"error": d.get("error", d), "latency": dt}
    u = d.get("usage", {})
    return {
        "content": d["choices"][0]["message"]["content"] or "",
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "cost": u.get("cost"),
        "latency": dt,
        "provider": d.get("provider"),
    }


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    return m.group(1) if m else text


def grade(task, output):
    g = task["grader"]
    t = g["type"]
    if t == "exact":
        return g["expected"].strip().lower() in output.strip().lower()
    if t == "numeric":
        m = re.findall(r"ANSWER:\s*(-?\d+(?:\.\d+)?)", output)
        if not m:
            m = re.findall(r"(-?\d+(?:\.\d+)?)", output)
        if not m:
            return False
        try:
            return abs(float(m[-1]) - g["expected"]) <= g["tol"]
        except ValueError:
            return False
    if t == "json_fields":
        m = re.search(r"\{.*\}", output, re.S)
        if not m:
            return False
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return False
        for k, v in g["fields"].items():
            if k not in obj:
                return False
            if isinstance(v, float):
                try:
                    if abs(float(obj[k]) - v) > 0.001:
                        return False
                except (TypeError, ValueError):
                    return False
            else:
                if str(obj[k]).strip() != str(v).strip():
                    return False
        return True
    if t == "code":
        code = extract_code(output)
        harness = code + "\n\nimport json\n_cases = json.loads(r'''" + json.dumps(g["cases"]) + "''')\n"
        harness += (
            "for _c in _cases:\n"
            "    _args, _exp = _c[0], _c[1]\n"
            f"    _got = {g['entry']}(*_args)\n"
            "    if isinstance(_got, list):\n"
            "        _got = json.loads(json.dumps(_got))\n"
            "    if _got != _exp:\n"
            "        raise SystemExit(1)\n"
            "print('OK')\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(harness)
            path = f.name
        try:
            r = subprocess.run([sys.executable, path], capture_output=True, timeout=10)
            return r.returncode == 0 and b"OK" in r.stdout
        except subprocess.TimeoutExpired:
            return False
        finally:
            os.unlink(path)
    return False


def main():
    model, key_env = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else model.split("/")[-1]
    key = os.environ.get(key_env)
    if not key:
        print(f"ERROR: env var {key_env} not set")
        sys.exit(2)
    tasks = json.load(open(GOLDEN))
    rows = []
    for task in tasks:
        res = call(model, key, task["prompt"])
        if "error" in res:
            print(f"[{task['id']}] CALL ERROR: {str(res['error'])[:100]}")
            rows.append({"id": task["id"], "category": task["category"], "label": label,
                         "model": model, "passed": False, "error": True,
                         "cost": 0, "prompt_tokens": 0, "completion_tokens": 0,
                         "latency": res.get("latency", 0)})
            continue
        passed = grade(task, res["content"])
        rows.append({"id": task["id"], "category": task["category"], "label": label,
                     "model": model, "passed": bool(passed),
                     "cost": res["cost"] or 0,
                     "prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"],
                     "latency": round(res["latency"], 2), "provider": res.get("provider")})
        print(f"[{task['id']:12}] {task['category']:20} {'PASS' if passed else 'FAIL':5} "
              f"cost=${res['cost']:.5f} out_tok={res['completion_tokens']} {res['latency']:.1f}s")

    with open(os.path.join(HERE, "results.jsonl"), "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    total_cost = sum(r["cost"] for r in rows)
    total_out = sum((r["completion_tokens"] or 0) for r in rows)
    avg_lat = sum(r["latency"] for r in rows) / n if n else 0
    cpst = total_cost / passed if passed else float("inf")
    summary = {
        "label": label, "model": model, "n_tasks": n, "passed": passed,
        "pass_rate": round(passed / n, 3) if n else 0,
        "total_cost_usd": round(total_cost, 6),
        "total_output_tokens": total_out,
        "avg_latency_s": round(avg_lat, 2),
        "cost_per_solved_task_usd": round(cpst, 6) if passed else None,
    }
    json.dump(summary, open(os.path.join(HERE, f"summary_{label}.json"), "w"), indent=2)
    print("\n=== SUMMARY", label, "===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
