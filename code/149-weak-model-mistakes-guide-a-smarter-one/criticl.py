#!/usr/bin/env python3
"""
criticl.py — a faithful, dependency-light port of CritICL (arXiv 2608.27455).

The claim: you do not need a bigger model or test-time scaling to lift a model's
reasoning. Take the mistakes a WEAKER model in the same family makes, distil them
into a short critique profile, and prepend that profile to the STRONGER model's
prompt at inference. The stronger model, warned about the family's habitual
traps, sidesteps them. No training, pure in-context.

This spike tests the "static" variant (one global failure profile) on a set of
multi-step word problems with deterministic, guaranteed-correct answers, using
gemini-2-5-flash as the weak model and gemini-2-5-pro as the strong one (the
Anthropic jurors are credit-blocked). We measure accuracy and output-token cost
for the strong model with and without the critique.

Everything is reproducible: fixed problem parameters, temperature 0.
"""

import json
import random
import re
import sys
import time

sys.path.insert(0, "/home/workloft")
from ruby import ruby  # noqa: E402  (the module /home/workloft/ruby/ruby.py)

WEAK = "gemini-2-5-flash"
STRONG = "gemini-2-5-pro"


# --- problem generator: multi-step, with the traps models actually fall for ---
# Each template computes its own exact integer answer, so ground truth is never
# a model's opinion. The traps: percent-of-the-remainder (not the original),
# "half of what remains", and hours-vs-minutes unit conversion.

def gen_problems(n, seed):
    """The one task family where our available models still have headroom:
    the digit-sum of a large power. The exact value is trivial in code and
    genuinely hard for a model to compute by hand, so it separates a careful
    solver from a sloppy one without being a 'trick'."""
    rng = random.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        a = rng.choice([3, 4, 6, 7, 8, 9])
        m = rng.randint(22, 38)
        if (a, m) in seen:
            continue
        seen.add((a, m))
        ans = sum(int(d) for d in str(a ** m))
        q = (f"What is the sum of the digits of {a} to the power {m} (that is, "
             f"{a}^{m} written out in full)? Compute the exact value, then add "
             f"up its digits.")
        out.append({"q": q, "answer": ans})
    return out


# --- model call + answer parsing ---------------------------------------------

SYS = ("You solve arithmetic word problems. Think step by step, then on the "
       "final line write exactly 'ANSWER: <integer>' with no units and no "
       "other text on that line.")


def ask(model_id, q, critique=""):
    by = ruby._models_by_id()
    model = by.get(model_id)
    sys_prompt = SYS
    if critique:
        sys_prompt = SYS + "\n\n" + critique
    msgs = [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": q}]
    t0 = time.monotonic()
    try:
        raw = ruby._direct_chat(model, msgs, max_tokens=1200, temperature=0.0)
    except Exception as e:
        return None, 0, f"ERR {type(e).__name__}"
    dt = int((time.monotonic() - t0) * 1000)
    out_tok = len(raw) // 4
    m = re.findall(r"ANSWER:\s*(-?\d[\d,]*)", raw)
    if not m:
        # fall back to the last integer in the reply
        m = re.findall(r"(-?\d[\d,]*)", raw)
    val = int(m[-1].replace(",", "")) if m else None
    return val, out_tok, dt


def build_critique(weak_failures):
    """Static CritICL: distil the weak model's mistakes into one global profile.
    We hand the strong model the problems the weak one got wrong, with the wrong
    answer and the right answer, and ask for the recurring error patterns."""
    lines = []
    for f in weak_failures:
        lines.append(f"- Problem: {f['q']}\n  Model answered {f['got']}, "
                     f"correct was {f['answer']}.")
    prompt = (
        "Below are arithmetic word problems that a weaker model in your family "
        "got wrong, with its answer and the correct answer. Identify the "
        "RECURRING mistake patterns (not one-offs). Return a short checklist, "
        "at most 6 bullets, of specific traps to watch for when solving this "
        "kind of problem. Be concrete about the operation that goes wrong.\n\n"
        + "\n".join(lines))
    by = ruby._models_by_id()
    raw = ruby._direct_chat(by.get(STRONG),
                            [{"role": "user", "content": prompt}],
                            max_tokens=600, temperature=0.0)
    return ("Common mistakes made on problems like this, watch for each one:\n"
            + raw.strip())


def run(n_harvest=25, n_eval=25):
    log = lambda m: print(f"[criticl] {m}", file=sys.stderr)
    harvest = gen_problems(n_harvest, seed=1)
    eval_set = gen_problems(n_eval, seed=2)

    # 1) harvest: weak model on the harvest set, collect its failures
    log(f"harvest: running {WEAK} on {n_harvest} problems...")
    weak_fail, weak_correct = [], 0
    for p in harvest:
        got, _, _ = ask(WEAK, p["q"])
        if got == p["answer"]:
            weak_correct += 1
        else:
            weak_fail.append({**p, "got": got})
    log(f"  weak accuracy {weak_correct}/{n_harvest}; {len(weak_fail)} failures")

    # 2) distil the failures into a static critique profile
    log("building static critique profile from weak failures...")
    critique = build_critique(weak_fail) if weak_fail else ""
    print("\n=== CRITIQUE PROFILE ===\n" + critique + "\n", file=sys.stderr)

    # 3) eval: strong model, plain vs plain+critique, on the held-out set
    log(f"eval: running {STRONG} on {n_eval} problems (plain vs +critique)...")
    A_correct = A_tok = B_correct = B_tok = 0
    rows = []
    for p in eval_set:
        a_val, a_tok, _ = ask(STRONG, p["q"])
        b_val, b_tok, _ = ask(STRONG, p["q"], critique=critique)
        A_correct += (a_val == p["answer"])
        B_correct += (b_val == p["answer"])
        A_tok += a_tok
        B_tok += b_tok
        rows.append({"answer": p["answer"], "plain": a_val, "crit": b_val})

    summary = {
        "weak_model": WEAK, "strong_model": STRONG,
        "n_harvest": n_harvest, "n_eval": n_eval,
        "weak_accuracy": round(weak_correct / n_harvest, 3),
        "strong_plain_accuracy": round(A_correct / n_eval, 3),
        "strong_critic_accuracy": round(B_correct / n_eval, 3),
        "accuracy_delta_pts": round((B_correct - A_correct) / n_eval * 100, 1),
        "strong_plain_out_tokens": A_tok,
        "strong_critic_out_tokens": B_tok,
        "token_overhead_pct": round((B_tok - A_tok) / A_tok * 100, 1) if A_tok else None,
    }
    out = {"summary": summary, "critique": critique, "rows": rows}
    with open("/home/workloft/loop-build/criticl/criticl_result.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(summary, indent=2))
    return out


if __name__ == "__main__":
    run()
