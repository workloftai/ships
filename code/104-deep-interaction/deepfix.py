#!/usr/bin/env python3
"""deepfix - repair an agent's reasoning, then distil the repair into a reusable rule.

Most agent fixes are thrown away. The model reasons its way into the same wrong
turn tomorrow that it took today, so the operator pastes the same correction into
context again, and again, growing the prompt every time. deepfix does the
opposite: you edit the one reasoning step that went wrong, then distil that edit
into a short directive that prevents the whole class of error on future runs, for
a fraction of the tokens.

Four verbs:

  edit    record a human correction to one reasoning step of a captured trace
  distil  turn that correction into a compact, reusable directive (needs a model)
  apply   compose the next run's prompt with accumulated directives prepended
  cost    compare carrying the fix inline every run vs the distilled directive

The compression is the model's job. Without --llm, distil is honest about it:
it stores the correction verbatim and cost will show ~no saving. Bring a model
and the directive shrinks to a rule, and the saving becomes real and permanent.

No third-party runtime dependencies. Token counting uses tiktoken if present,
otherwise a documented characters/4 estimate (flagged in output).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict, field
from pathlib import Path


# --------------------------------------------------------------------------- #
# token counting
# --------------------------------------------------------------------------- #

def count_tokens(text: str) -> tuple[int, bool]:
    """Return (token_count, is_exact). Exact when tiktoken is installed."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), True
    except Exception:
        # Documented fallback: ~4 chars per token for English prose.
        return max(1, round(len(text) / 4)), False


# --------------------------------------------------------------------------- #
# data model
# --------------------------------------------------------------------------- #

@dataclass
class Correction:
    step_id: int
    before: str          # the reasoning as the model wrote it
    after: str           # the reasoning as the human rewrote it


@dataclass
class Directive:
    rule: str            # the reusable, compressed instruction
    source_step: int     # which step it came from
    verbatim: bool = False  # True when no model was used to distil (no compression)


@dataclass
class Trace:
    task: str
    steps: list[dict] = field(default_factory=list)
    answer: str = ""
    correction: dict | None = None   # a Correction, once edited

    @classmethod
    def load(cls, path: str | Path) -> "Trace":
        data = json.loads(Path(path).read_text())
        return cls(
            task=data["task"],
            steps=data.get("steps", []),
            answer=data.get("answer", ""),
            correction=data.get("correction"),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict_trace(self), indent=2) + "\n")

    def step(self, step_id: int) -> dict:
        for s in self.steps:
            if s.get("id") == step_id:
                return s
        raise KeyError(f"no step with id {step_id} in trace")


def asdict_trace(t: Trace) -> dict:
    d = {"task": t.task, "steps": t.steps, "answer": t.answer}
    if t.correction is not None:
        d["correction"] = t.correction
    return d


# --------------------------------------------------------------------------- #
# core verbs (importable, no I/O side effects beyond what is passed in)
# --------------------------------------------------------------------------- #

def edit(trace: Trace, step_id: int, corrected: str) -> Correction:
    """Record a human rewrite of one reasoning step. Returns the Correction."""
    original = trace.step(step_id).get("thought", "")
    corr = Correction(step_id=step_id, before=original, after=corrected)
    trace.correction = asdict(corr)
    return corr


def distil(correction: Correction, use_llm: bool, model: str = "claude-haiku-4-5-20251001") -> Directive:
    """Turn a one-off correction into a reusable rule.

    With use_llm the model writes the general rule that would have prevented the
    error. Without it, the correction is stored verbatim (no compression) and the
    directive is flagged verbatim=True so downstream code can be honest about it.
    """
    if not use_llm:
        return Directive(rule=correction.after.strip(), source_step=correction.step_id, verbatim=True)

    prompt = (
        "An AI agent made a reasoning error, and a human corrected it.\n\n"
        f"WRONG reasoning step:\n{correction.before}\n\n"
        f"HUMAN correction:\n{correction.after}\n\n"
        "Write ONE short, general directive (a single sentence, imperative mood) that "
        "would stop an agent making this class of error in future. State the rule and "
        "its scope. Do not mention this specific case. Reply with the directive only, "
        "no preamble, no quotes."
    )
    rule = _call_claude(prompt, model=model).strip().strip('"')
    return Directive(rule=rule, source_step=correction.step_id, verbatim=False)


def apply(task: str, directives: list[Directive]) -> str:
    """Compose the next run's prompt: directives preamble, then the task."""
    if not directives:
        return task
    lines = ["Standing directives (learned from earlier corrections):"]
    for i, d in enumerate(directives, 1):
        lines.append(f"{i}. {d.rule}")
    lines.append("")
    lines.append(f"Task: {task}")
    return "\n".join(lines)


def cost(correction: Correction, directive: Directive, runs: int = 100) -> dict:
    """Compare carrying the fix inline every run vs injecting the distilled rule.

    inline  = re-paste the full worked correction into context on every run
    distil  = inject the distilled directive on every run
    """
    inline_text = correction.after.strip()
    inline_t, exact_a = count_tokens(inline_text)
    rule_t, exact_b = count_tokens(directive.rule)
    exact = exact_a and exact_b
    per_run_saved = inline_t - rule_t
    pct = (per_run_saved / inline_t * 100) if inline_t else 0.0
    return {
        "inline_tokens_per_run": inline_t,
        "directive_tokens_per_run": rule_t,
        "saved_per_run": per_run_saved,
        "saved_pct": round(pct, 1),
        "saved_over_runs": per_run_saved * runs,
        "runs": runs,
        "exact_tokeniser": exact,
        "verbatim_directive": directive.verbatim,
    }


# --------------------------------------------------------------------------- #
# minimal Claude client (stdlib only)
# --------------------------------------------------------------------------- #

def _load_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # convenience: read the fleet tier-keys file if present
    env = Path.home() / "larry-tier-routing" / ".env.tier-keys"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("ANTHROPIC_API_KEY not set (env or ~/larry-tier-routing/.env.tier-keys)")


def _call_claude(prompt: str, model: str, max_tokens: int = 300) -> str:
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": _load_key(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data.get("content", []))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Claude API {e.code}: {e.read().decode()[:200]}") from e


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _cmd_edit(args) -> None:
    trace = Trace.load(args.trace)
    corr = edit(trace, args.step, args.to)
    trace.save(args.trace)
    print(f"recorded correction to step {corr.step_id} of {args.trace}")
    print(f"  before: {corr.before[:80]}...")
    print(f"  after : {corr.after[:80]}...")


def _cmd_distil(args) -> None:
    trace = Trace.load(args.trace)
    if not trace.correction:
        sys.exit("no correction on this trace; run `edit` first")
    corr = Correction(**trace.correction)
    d = distil(corr, use_llm=args.llm, model=args.model)
    out = Path(args.out)
    existing = json.loads(out.read_text()) if out.exists() else []
    existing.append(asdict(d))
    out.write_text(json.dumps(existing, indent=2) + "\n")
    tag = "verbatim (no model, no compression)" if d.verbatim else f"distilled via {args.model}"
    print(f"directive [{tag}]:")
    print(f"  {d.rule}")
    print(f"appended to {args.out} ({len(existing)} total)")


def _cmd_apply(args) -> None:
    directives = [Directive(**x) for x in json.loads(Path(args.directives).read_text())]
    print(apply(args.task, directives))


def _cmd_cost(args) -> None:
    trace = Trace.load(args.trace)
    if not trace.correction:
        sys.exit("no correction on this trace; run `edit` first")
    corr = Correction(**trace.correction)
    directives = [Directive(**x) for x in json.loads(Path(args.directives).read_text())]
    d = directives[-1]
    r = cost(corr, d, runs=args.runs)
    approx = "" if r["exact_tokeniser"] else "  (approx: install tiktoken for exact counts)"
    print(f"inline fix per run   : {r['inline_tokens_per_run']} tokens{approx}")
    print(f"distilled per run    : {r['directive_tokens_per_run']} tokens")
    print(f"saved per run        : {r['saved_per_run']} tokens ({r['saved_pct']}%)")
    print(f"saved over {r['runs']} runs   : {r['saved_over_runs']} tokens")
    if r["verbatim_directive"]:
        print("note: directive is verbatim (distilled without a model), so there is no compression.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deepfix", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("edit", help="record a human correction to a reasoning step")
    pe.add_argument("trace")
    pe.add_argument("--step", type=int, required=True)
    pe.add_argument("--to", required=True, help="the corrected reasoning")
    pe.set_defaults(func=_cmd_edit)

    pd = sub.add_parser("distil", help="turn the correction into a reusable directive")
    pd.add_argument("trace")
    pd.add_argument("--out", default="directives.json")
    pd.add_argument("--llm", action="store_true", help="use a model to compress the rule")
    pd.add_argument("--model", default="claude-haiku-4-5-20251001")
    pd.set_defaults(func=_cmd_distil)

    pa = sub.add_parser("apply", help="compose next run's prompt with directives")
    pa.add_argument("task")
    pa.add_argument("--directives", default="directives.json")
    pa.set_defaults(func=_cmd_apply)

    pc = sub.add_parser("cost", help="inline-every-run vs distilled-directive tokens")
    pc.add_argument("trace")
    pc.add_argument("--directives", default="directives.json")
    pc.add_argument("--runs", type=int, default=100)
    pc.set_defaults(func=_cmd_cost)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
