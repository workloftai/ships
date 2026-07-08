#!/usr/bin/env python3
"""
disagree.py - two lineages review the same diff; surface only where they differ.

Claude wrote the code, then reviews it. OpenAI Codex reviews it blind. Findings
both lineages raise are probably real, so they need no argument. Findings only
one raises are the whole point: either the other lineage missed a real bug, or
the finding is noise. That disagreement is the only thing worth a human's eyes.

    CLAUDE + CODEX agree   -> trust it, act
    CLAUDE only            -> Codex missed it, or Claude is over-flagging
    CODEX only             -> Claude's blind spot, or Codex is over-flagging

Reuses the Codex path from codex_review.py and adds a Claude reviewer via the
Anthropic API. Both outputs are schema-validated before they are compared; a
finding neither lineage can state cleanly does not get to vote.

    cat change.diff | python3 disagree.py --stdin
    python3 disagree.py --path src/api/handler.py --json

Needs: codex CLI authenticated, and ANTHROPIC_API_KEY (read from env or
~/conexus/.env).
"""

import argparse
import json
import os
import re
import sys
import urllib.request

import codex_review as cr

CLAUDE_MODEL = "claude-sonnet-4-6"
STOP = {"the", "a", "an", "in", "of", "to", "and", "is", "it", "on", "for",
        "with", "that", "this", "code", "value", "when", "into", "from", "as"}


def load_anthropic_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k
    for path in ("/home/workloft/conexus/.env",
                 "/home/workloft/larry-tier-routing/.env.tier-keys"):
        try:
            for line in open(path):
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return None


def claude_review(target_block, key, timeout=120):
    """Ask Claude to review the same target, returning validated findings."""
    prompt = cr.REVIEW_PROMPT.format(target=target_block) + (
        '\n\nReturn ONLY a JSON object of the form '
        '{"findings": [{"severity","file","line","title","why","confidence"}]}.'
    )
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json",
                 "x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e:  # noqa: BLE001 - report and degrade, do not crash
        sys.stderr.write(f"disagree: claude review failed: {e}\n")
        return None
    text = "".join(b.get("text", "") for b in resp.get("content", []))
    obj = cr.extract_json(text)
    if not obj or "findings" not in obj:
        return []
    return [v for v in (cr.validate_finding(f) for f in obj["findings"]) if v]


def keywords(finding):
    words = re.findall(r"[a-z_]+", (finding["title"] + " " + finding["why"]).lower())
    return {w for w in words if len(w) > 3 and w not in STOP}


def same_bug(a, b):
    """Two findings describe the same defect: same file and overlapping mechanism."""
    fa, fb = a["file"].split("/")[-1], b["file"].split("/")[-1]
    if fa and fb and fa != fb:
        return False
    return len(keywords(a) & keywords(b)) >= 2


def reconcile(claude, codex):
    agreed, claude_only, matched_codex = [], [], set()
    for cf in claude:
        hit = next((i for i, xf in enumerate(codex)
                    if i not in matched_codex and same_bug(cf, xf)), None)
        if hit is None:
            claude_only.append(cf)
        else:
            matched_codex.add(hit)
            agreed.append({"claude": cf, "codex": codex[hit]})
    codex_only = [xf for i, xf in enumerate(codex) if i not in matched_codex]
    return agreed, claude_only, codex_only


def main():
    ap = argparse.ArgumentParser(description="Surface only cross-lineage disagreements.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--stdin", action="store_true")
    src.add_argument("--path", nargs="+")
    ap.add_argument("--min-severity", default="MEDIUM", choices=list(cr.SEVERITY_RANK))
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    key = load_anthropic_key()
    if not key:
        sys.exit("disagree: no ANTHROPIC_API_KEY found")

    target = cr.build_target_block(args)

    # Codex (blind, different lineage) and Claude (the author's lineage).
    raw, err = cr.run_codex(cr.REVIEW_PROMPT.format(target=target),
                            args.model, args.effort, 900)
    codex = []
    if err:
        sys.stderr.write(f"disagree: codex review failed: {err}\n")
    else:
        obj = cr.extract_json(raw) or {}
        codex = [v for v in (cr.validate_finding(f) for f in obj.get("findings", [])) if v]
    claude = claude_review(target, key) or []

    floor = cr.SEVERITY_RANK[args.min_severity]

    def gate(fs):
        return [f for f in fs if cr.SEVERITY_RANK[f["severity"]] >= floor
                and f["confidence"] >= args.min_confidence]

    claude, codex = gate(claude), gate(codex)
    agreed, claude_only, codex_only = reconcile(claude, codex)

    if args.json:
        print(json.dumps({
            "agreed": agreed, "claude_only": claude_only,
            "codex_only": codex_only,
        }, indent=2))
        return 2 if (claude_only or codex_only) else 0

    print(f"Two lineages reviewed the same change.\n")
    print(f"  AGREED ({len(agreed)}): trust these, both lineages raised them")
    for m in agreed:
        print(f"    [{m['codex']['severity']}] {m['claude']['title']}")
    print(f"\n  DISAGREEMENT is the signal below - one lineage saw it, the other did not:\n")
    print(f"  CLAUDE ONLY ({len(claude_only)}) - Codex missed it, or Claude over-flagged:")
    for f in claude_only:
        print(f"    [{f['severity']}] ({f['confidence']}) {f['file']}: {f['title']}")
    print(f"\n  CODEX ONLY ({len(codex_only)}) - Claude's blind spot, or Codex over-flagged:")
    for f in codex_only:
        print(f"    [{f['severity']}] ({f['confidence']}) {f['file']}: {f['title']}")
    return 2 if (claude_only or codex_only) else 0


if __name__ == "__main__":
    sys.exit(main())
