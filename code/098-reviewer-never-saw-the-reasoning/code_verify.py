#!/usr/bin/env python3
"""
code_verify.py - a cross-lineage juror that verifies a claim about a change.

Our eval panel (Vera) votes on text with jurors from different lineages. This is
the same idea pointed at code: given a change and a claim about it, a GPT-lineage
model reads the actual diff and rules on whether the claim holds. Verification is
the thing agents are worst at, "it looks fixed" is not "it fixes the root cause",
so the juror is told to try to refute the claim, not confirm it.

    python3 code_verify.py --claim "this fixes the N+1 query on the orders page" \
        --path src/orders.py

    git diff | python3 code_verify.py --claim "adds expiry check, no regression" --stdin

Verdict is one of confirmed / refuted / uncertain, with a reason, a confidence,
and any regressions the change introduces. Designed to slot next to Vera's text
jurors as a code juror: same shape (verdict + confidence + reason), same rule
(default to refuted when unsure). Exit code 2 = not confirmed (a CI-blockable
signal), 0 = confirmed, 1 = the juror failed to run.
"""

import argparse
import json
import sys

import codex_review as cr

VERDICTS = ("confirmed", "refuted", "uncertain")

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "regressions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "confidence", "reason", "regressions"],
    "additionalProperties": False,
}

VERIFY_PROMPT = """\
You are a code verifier from a different lineage than the author. You are not
here to be agreeable. A claim has been made about a code change. Your job is to
try to REFUTE it by reading the actual code, and to confirm it only if you
cannot.

Claim: {claim}

Rules:
- "confirmed" only if the change genuinely achieves the claim at the root cause,
  not just on the happy path.
- "refuted" if the change does not achieve the claim, achieves it only
  partially, or introduces a regression that undermines it.
- "uncertain" if you cannot tell from what you can see. Default here when in
  doubt; do not confirm to be helpful.
- List any regressions the change introduces, even if the claim itself holds.

{target}

Return your verdict in the required JSON shape and nothing else.
"""


def main():
    ap = argparse.ArgumentParser(description="Cross-lineage verifier for a code claim.")
    ap.add_argument("--claim", required=True, help="the claim to verify")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--stdin", action="store_true", help="read a diff from stdin")
    src.add_argument("--path", nargs="+", help="files or dirs to read")
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--effort", default="high",
                    choices=["low", "medium", "high", "xhigh"])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    target = cr.build_target_block(args)
    prompt = VERIFY_PROMPT.format(claim=args.claim, target=target)

    # Reuse the Codex path but with the verification schema.
    import tempfile, os, subprocess
    with tempfile.TemporaryDirectory() as td:
        schema_path = os.path.join(td, "schema.json")
        out_path = os.path.join(td, "last.json")
        with open(schema_path, "w") as fh:
            json.dump(VERIFY_SCHEMA, fh)
        cmd = [
            "codex", "exec", "--sandbox", "read-only", "--ephemeral",
            "--skip-git-repo-check", "--color", "never",
            "-c", f'model="{args.model}"',
            "-c", f'model_reasoning_effort="{args.effort}"',
            "--output-schema", schema_path,
            "--output-last-message", out_path, prompt,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           timeout=args.timeout, stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"code_verify: juror failed: {e}", file=sys.stderr)
            return 1
        raw = open(out_path).read() if os.path.exists(out_path) else ""

    obj = cr.extract_json(raw)
    if not obj or obj.get("verdict") not in VERDICTS:
        print("code_verify: juror returned no usable verdict", file=sys.stderr)
        return 1
    try:
        conf = round(float(obj["confidence"]), 2)
    except (TypeError, ValueError):
        conf = 0.0
    verdict = obj["verdict"]
    reason = str(obj.get("reason", "")).strip()
    regressions = [str(r).strip() for r in obj.get("regressions", []) if str(r).strip()]

    if args.json:
        print(json.dumps({"verdict": verdict, "confidence": conf,
                          "reason": reason, "regressions": regressions}, indent=2))
    else:
        print(f"Claim: {args.claim}")
        print(f"Verdict: {verdict.upper()}  (confidence {conf})")
        print(f"Reason: {reason}")
        if regressions:
            print("Regressions:")
            for r in regressions:
                print(f"  - {r}")
    return 0 if verdict == "confirmed" else 2


if __name__ == "__main__":
    sys.exit(main())
