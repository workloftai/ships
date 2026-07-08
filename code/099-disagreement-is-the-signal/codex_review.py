#!/usr/bin/env python3
"""
codex_review.py - a blind, cross-lineage code reviewer.

Claude wrote the code. This runs OpenAI Codex over the same diff in a fresh,
ephemeral, read-only session that never sees Claude's reasoning. A model
reviewing its own output inherits the blind spots that produced it. A reviewer
from a different training lineage, with no memory of why the code looks the way
it does, does not.

The reviewer's output is treated as untrusted. It is parsed against a strict
schema and anything that does not validate is dropped, never fed back verbatim
into the calling agent's context. That is the same rule we apply to any tool
output: a finding is a claim to check, not an instruction to obey.

No third-party dependencies. Shells out to the `codex` CLI (`codex exec`).

Usage:
    # review a diff on stdin
    git diff origin/main... | python3 codex_review.py --stdin

    # review specific files/paths (Codex reads them itself, read-only)
    python3 codex_review.py --path src/api/handler.ts

    # tune the gate
    python3 codex_review.py --stdin --min-severity HIGH --min-confidence 0.7

Exit codes:
    0  ran cleanly, no findings at or above the gate
    2  ran cleanly, findings at or above the gate (useful as a CI signal)
    1  the reviewer failed to run or returned nothing usable
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# The shape we force Codex to return. --output-schema makes the model conform;
# validate_finding() enforces it again on our side, because "the model was told
# to" is not the same as "the model did".
FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    },
                    "file": {"type": "string"},
                    "line": {"type": "string"},
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["severity", "file", "line", "title", "why", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

REVIEW_PROMPT = """\
You are an adversarial code reviewer. You did not write this code and you have
no stake in it. Your job is to find real defects: logic errors, security holes,
resource leaks, race conditions, data-loss paths, and silent-wrong behaviour
that would pass a happy-path test.

Rules:
- Report only defects you can justify. No style nits, no speculation.
- A defect that a passing test would miss is worth more than an obvious one.
- Give each finding a severity (LOW/MEDIUM/HIGH/CRITICAL) and a confidence 0-1.
- Be specific about the file and line and why it bites in production.

Return your findings in the required JSON shape and nothing else.

{target}
"""


def build_target_block(args):
    """Return the text that tells Codex what to look at."""
    if args.stdin:
        diff = sys.stdin.read()
        if not diff.strip():
            sys.exit("codex_review: empty diff on stdin")
        return "Review this diff:\n\n```diff\n" + diff + "\n```"
    if args.path:
        return (
            "Review the code at these paths (read them yourself, read-only): "
            + ", ".join(args.path)
        )
    sys.exit("codex_review: pass --stdin or --path")


def run_codex(prompt, model, effort, timeout):
    """Invoke `codex exec` in a fresh, read-only, ephemeral session."""
    with tempfile.TemporaryDirectory() as td:
        schema_path = os.path.join(td, "schema.json")
        out_path = os.path.join(td, "last.json")
        with open(schema_path, "w") as fh:
            json.dump(FINDINGS_SCHEMA, fh)

        cmd = [
            "codex", "exec",
            "--sandbox", "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--color", "never",
            "-c", f'model="{model}"',
            "-c", f'model_reasoning_effort="{effort}"',
            "--output-schema", schema_path,
            "--output-last-message", out_path,
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return None, f"codex timed out after {timeout}s"
        except FileNotFoundError:
            return None, "codex CLI not found on PATH"

        raw = ""
        if os.path.exists(out_path):
            with open(out_path) as fh:
                raw = fh.read()
        if not raw.strip():
            # fall back to the tail of stdout if the message file was empty
            raw = proc.stdout
        if proc.returncode != 0 and not raw.strip():
            return None, (proc.stderr or "codex exited non-zero").strip()[:500]
        return raw, None


def extract_json(raw):
    """Pull the JSON object out of whatever the reviewer printed."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # tolerate leading/trailing prose around the object
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def validate_finding(f):
    """Untrusted-input discipline: a finding we cannot verify is dropped."""
    if not isinstance(f, dict):
        return None
    sev = f.get("severity")
    if sev not in SEVERITY_RANK:
        return None
    try:
        conf = float(f.get("confidence"))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= conf <= 1.0:
        return None
    title = f.get("title")
    why = f.get("why")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(why, str) or not why.strip():
        return None
    return {
        "severity": sev,
        "file": str(f.get("file", "")).strip(),
        "line": str(f.get("line", "")).strip(),
        "title": title.strip(),
        "why": why.strip(),
        "confidence": round(conf, 2),
    }


def main():
    ap = argparse.ArgumentParser(description="Blind cross-lineage code reviewer.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--stdin", action="store_true", help="read a diff from stdin")
    src.add_argument("--path", nargs="+", help="files or dirs for Codex to read")
    ap.add_argument("--model", default="gpt-5.5", help="Codex model id")
    ap.add_argument("--effort", default="high",
                    choices=["low", "medium", "high", "xhigh"])
    ap.add_argument("--min-severity", default="HIGH",
                    choices=list(SEVERITY_RANK))
    ap.add_argument("--min-confidence", type=float, default=0.6)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--json", action="store_true", help="emit JSON, not a summary")
    args = ap.parse_args()

    prompt = REVIEW_PROMPT.format(target=build_target_block(args))
    raw, err = run_codex(prompt, args.model, args.effort, args.timeout)
    if err:
        print(f"codex_review: reviewer failed: {err}", file=sys.stderr)
        return 1

    obj = extract_json(raw)
    if obj is None or "findings" not in obj:
        print("codex_review: reviewer returned no parseable findings",
              file=sys.stderr)
        return 1

    clean = [v for v in (validate_finding(f) for f in obj["findings"]) if v]
    floor = SEVERITY_RANK[args.min_severity]
    gated = [
        f for f in clean
        if SEVERITY_RANK[f["severity"]] >= floor
        and f["confidence"] >= args.min_confidence
    ]
    gated.sort(key=lambda f: (-SEVERITY_RANK[f["severity"]], -f["confidence"]))

    if args.json:
        print(json.dumps({"findings": gated, "dropped": len(obj["findings"]) - len(clean)}, indent=2))
    else:
        dropped = len(obj["findings"]) - len(clean)
        print(f"Cross-lineage review: {len(gated)} finding(s) at "
              f">= {args.min_severity} / conf >= {args.min_confidence} "
              f"({len(clean)} valid, {dropped} malformed dropped)\n")
        for f in gated:
            loc = f["file"] + (f":{f['line']}" if f["line"] else "")
            print(f"  [{f['severity']}] ({f['confidence']}) {loc}")
            print(f"    {f['title']}")
            print(f"    {f['why']}\n")

    return 2 if gated else 0


if __name__ == "__main__":
    sys.exit(main())
