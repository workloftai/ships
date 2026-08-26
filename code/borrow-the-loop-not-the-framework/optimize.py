"""A self-tuning prompt-optimisation loop, in about 110 lines, with no framework.

This is the companion code to Workloft Labs Note No. 76, "We Rebuilt a Research
Paper's Self-Tuning Loop in 110 Lines":
    https://workloft.ai/labs/notes/borrow-the-loop-not-the-framework-2026-08-26.html

Two papers ship the same idea wrapped in a lot of apparatus:
  - FAPO (Cisco Foundation AI):        https://arxiv.org/abs/2606.19605
  - AutoSaddler:                       https://arxiv.org/abs/2608.23041

The idea underneath both is a five-step loop:
    evaluate a prompt on a dataset
      -> attribute the single dominant failure
      -> propose a targeted rewrite
      -> KEEP it only if it scores better
      -> repeat, bounded, stop at target.

That loop is the whole engine. It needs no cluster, no pipeline framework, and no
particular model provider. The only thing it needs from the outside world is a way
to call a model, which you inject as `chat_fn`. Bring your own: OpenAI, a local
open-weight model, anything that maps messages -> text. See demo.py for a reference
adapter. There is deliberately nothing to install here.

    from optimize import optimize, exact_match
    best_prompt, best_score, history = optimize(
        task_prompt="Answer the question.",
        dataset=[{"input": "Is the sky blue?", "expected": "yes"}, ...],
        chat_fn=my_chat_fn,
        scorer=exact_match, max_rounds=4, target=100)
"""
from __future__ import annotations

import re
from typing import Callable, Iterable

# A chat_fn takes a list of {"role", "content"} messages plus max_tokens and
# temperature, and returns the model's reply as a plain string. That is the only
# dependency this loop has on the outside world.
ChatFn = Callable[[list, int, float], str]


def exact_match(output: str, expected: str) -> int:
    """0 or 100, case-insensitive, trailing punctuation/quotes stripped."""
    def norm(s: str) -> str:
        return re.sub(r"[\s.!\"']+$", "", str(s).strip().lower())
    return 100 if norm(output) == norm(expected) else 0


def _run_prompt(chat_fn: ChatFn, prompt: str, case_input: str) -> str:
    msgs = [{"role": "system", "content": prompt},
            {"role": "user", "content": case_input}]
    try:
        return chat_fn(msgs, 200, 0.0).strip()
    except Exception as e:  # a task-model failure scores 0, it never crashes the loop
        return f"[error: {e}]"


def _evaluate(chat_fn: ChatFn, prompt: str, dataset: Iterable[dict], scorer):
    results = []
    for c in dataset:
        out = _run_prompt(chat_fn, prompt, c["input"])
        results.append({"input": c["input"], "expected": c["expected"],
                        "output": out, "score": scorer(out, c["expected"])})
    mean = sum(r["score"] for r in results) / max(1, len(results))
    return mean, results


def _attribute(chat_fn: ChatFn, failures: list) -> str:
    """One-sentence root cause of the dominant failure, from the failing cases."""
    sample = "\n".join(
        f"- Q: {f['input']!r} | model said: {f['output']!r} | expected: {f['expected']!r}"
        for f in failures[:8])
    msg = [{"role": "user", "content":
            "These cases FAILED an exact-match check. In ONE sentence, name the single "
            "dominant, specific, falsifiable root cause of failure:\n" + sample}]
    return chat_fn(msg, 120, 0.0).strip()


def _propose(chat_fn: ChatFn, prompt: str, diagnosis: str, failures: list) -> str:
    sample = "\n".join(
        f"- Q: {f['input']!r} -> expected {f['expected']!r}, got {f['output']!r}"
        for f in failures[:5])
    msg = [{"role": "user", "content":
            f"You are optimising a SYSTEM PROMPT for a task model.\n\nCURRENT PROMPT:\n{prompt}\n\n"
            f"DOMINANT FAILURE: {diagnosis}\n\nFAILING CASES:\n{sample}\n\n"
            "Rewrite the system prompt to fix that dominant failure. Keep it short and concrete. "
            "Return ONLY the new prompt text, no preamble, no quotes."}]
    return chat_fn(msg, 300, 0.3).strip().strip('"').strip()


def optimize(*, task_prompt: str, dataset: list, chat_fn: ChatFn, scorer=exact_match,
             max_rounds: int = 4, target: int = 100, verbose: bool = True):
    """Returns (best_prompt, best_score, history). Bounded by max_rounds; stops at target."""
    best_prompt = task_prompt
    best_score, results = _evaluate(chat_fn, best_prompt, dataset, scorer)
    history = [{"round": 0, "prompt": best_prompt, "score": best_score,
                "diagnosis": "(baseline)", "kept": True}]
    if verbose:
        print(f"[round 0] baseline score = {best_score:.0f}")
    for rnd in range(1, max_rounds + 1):
        if best_score >= target:
            if verbose:
                print(f"target {target} reached, stopping.")
            break
        failures = [r for r in results if r["score"] < target]
        if not failures:
            break
        diagnosis = _attribute(chat_fn, failures)
        candidate = _propose(chat_fn, best_prompt, diagnosis, failures)
        cand_score, cand_results = _evaluate(chat_fn, candidate, dataset, scorer)
        kept = cand_score > best_score  # keep ONLY if measured better. no vibes.
        if verbose:
            print(f"[round {rnd}] diagnosis: {diagnosis}")
            print(f"[round {rnd}] candidate = {candidate!r}")
            print(f"[round {rnd}] score = {cand_score:.0f}  ({'KEPT' if kept else 'rejected, worse'})")
        history.append({"round": rnd, "prompt": candidate, "score": cand_score,
                        "diagnosis": diagnosis, "kept": kept})
        if kept:
            best_prompt, best_score, results = candidate, cand_score, cand_results
    return best_prompt, best_score, history
