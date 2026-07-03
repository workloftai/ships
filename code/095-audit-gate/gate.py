#!/usr/bin/env python3
"""audit-gate — a diff-level audit gate for agent-written code.

Two stages, both must pass:

  Stage 0  Deterministic tripwires. Pure-Python scan of the diff for the
           classic agent cheats: disabled linters, stubbed implementations,
           skipped/focused tests, weakened CI. Any hit is a blocker and the
           gate FAILS before a single model token is spent.

  Stage 1  Independent LLM auditor. A fresh headless Claude session (no
           shared context with whoever wrote the code) reviews the diff
           against a rubric. Mandatory-findings rule: the auditor must
           return at least one finding OR an explicit justification for
           returning none. Neither -> the audit itself is invalid and the
           gate FAILS. An auditor that always says "looks good" is
           indistinguishable from no auditor.

Every verdict is appended to a hash-chained JSONL log. `verify-log` walks
the chain and reports the first broken link, so a verdict can't be quietly
rewritten after the fact.

Trial scope: fleet/internal repos only. Not wired to client repos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG = GATE_DIR / "log" / "audit-log.jsonl"
RUBRIC_PATH = GATE_DIR / "rubric.md"
GENESIS = "0" * 64
MAX_DIFF_CHARS = 60_000
LLM_TIMEOUT_S = 8 * 60

CI_FILE_RE = re.compile(
    r"(^|/)(\.gitlab-ci\.yml|\.github/workflows/[^/]+|Jenkinsfile|\.circleci/[^/]+)$"
)
TEST_FILE_RE = re.compile(r"(^|/)(tests?/|test_[^/]+\.py$|[^/]+[._](test|spec)\.[jt]sx?$)")
# Prose that MENTIONS a cheat pattern is not a cheat. Docs/content files are
# exempt from added-line tripwires (CI and test-deletion checks still apply).
DOCS_FILE_RE = re.compile(r"\.(md|markdown|rst|txt|html?)$", re.I)

# (id, description, regex applied to ADDED lines)
ADDED_LINE_TRIPWIRES = [
    ("lint-suppressed",
     "lint/type suppression added",
     re.compile(r"#\s*noqa|#\s*type:\s*ignore|eslint-disable|pylint:\s*disable"
                r"|@ts-ignore|@ts-nocheck|rubocop:disable", re.I)),
    ("stubbed",
     "stub or placeholder implementation added",
     re.compile(r"raise\s+NotImplementedError|not\s+implemented\s*yet"
                r"|#\s*(stub|placeholder)\b|//\s*(stub|placeholder)\b"
                r"|//\s*TODO:?\s*implement|#\s*TODO:?\s*implement", re.I)),
    ("test-skipped",
     "test skipped or suite narrowed",
     re.compile(r"@pytest\.mark\.skip|@unittest\.skip|\b(it|test|xit)\.skip\s*\("
                r"|\bxit\s*\(|\bxdescribe\s*\(|\b(it|test|describe)\.only\s*\(", )),
    ("verify-bypassed",
     "hook/verification bypass added",
     re.compile(r"--no-verify\b")),
]
CI_ADDED_TRIPWIRES = [
    ("ci-weakened",
     "CI weakened (failures tolerated)",
     re.compile(r"allow_failure:\s*true|continue-on-error:\s*true|\|\|\s*true\b", re.I)),
]
CI_REMOVED_TRIPWIRES = [
    ("ci-step-removed",
     "test/lint step removed from CI",
     re.compile(r"\b(pytest|npm\s+test|yarn\s+test|go\s+test|cargo\s+test|lint|ruff|eslint|tsc)\b", re.I)),
]


def sh(args: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def get_diff(repo: str, staged: bool, rng: str | None) -> str:
    if rng:
        return sh(["git", "diff", rng], cwd=repo)
    if staged:
        return sh(["git", "diff", "--cached"], cwd=repo)
    return sh(["git", "diff", "HEAD"], cwd=repo)


def scan_tripwires(diff: str) -> list[dict]:
    """Stage 0: deterministic refuse-to-pass scan over the diff."""
    findings = []
    current_file = ""
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if raw.startswith("deleted file mode") and TEST_FILE_RE.search(current_file or ""):
            findings.append(_trip("test-file-deleted", "test file deleted",
                                  current_file, raw))
            continue
        is_ci = bool(CI_FILE_RE.search(current_file or ""))
        is_docs = bool(DOCS_FILE_RE.search(current_file or ""))
        if raw.startswith("+") and not raw.startswith("+++"):
            line = raw[1:]
            if not is_docs:
                for tid, desc, rx in ADDED_LINE_TRIPWIRES:
                    if rx.search(line):
                        findings.append(_trip(tid, desc, current_file, line))
            if is_ci:
                for tid, desc, rx in CI_ADDED_TRIPWIRES:
                    if rx.search(line):
                        findings.append(_trip(tid, desc, current_file, line))
        elif raw.startswith("-") and not raw.startswith("---") and is_ci:
            line = raw[1:]
            for tid, desc, rx in CI_REMOVED_TRIPWIRES:
                if rx.search(line):
                    findings.append(_trip(tid, desc, current_file, line))
    return findings


def _trip(tid: str, desc: str, file: str, evidence: str) -> dict:
    return {"severity": "blocker", "deterministic": True, "id": tid,
            "file": file, "issue": desc, "evidence": evidence.strip()[:200]}


AUDITOR_PROMPT = """You are an independent code auditor. You did not write this \
change and you share no context with whoever did. Your job is to find what is \
wrong with it, not to approve it.

Audit the diff below against this rubric:

{rubric}

Rules, all binding:
- MANDATORY FINDINGS: return at least one finding (any severity), OR set \
"no_findings_justification" to a specific, evidence-based explanation of why \
this diff genuinely warrants none. An empty findings list with no \
justification is an invalid audit.
- Severity: "blocker" = must not merge (bug, security hole, silent behaviour \
change, dishonest test). "major" = wrong but survivable. "minor" = style/nit.
- Cite evidence: quote the exact added/removed line for every finding.
- You may read surrounding files in the working directory for context, but \
judge only the diff.
- Do not propose fixes. Verdict only.

Respond with ONLY a JSON object, no prose, no code fences:
{{"findings": [{{"severity": "blocker|major|minor", "file": "path", \
"issue": "...", "evidence": "quoted line"}}], \
"rubric": {{"correctness": "pass|fail", "tests": "pass|fail", \
"security": "pass|fail", "honesty": "pass|fail"}}, \
"no_findings_justification": null, \
"verdict": "pass|fail"}}

DIFF:
{diff}
"""


def run_llm_audit(diff: str, repo: str) -> dict:
    rubric = RUBRIC_PATH.read_text() if RUBRIC_PATH.exists() else "correctness, tests, security, honesty"
    prompt = AUDITOR_PROMPT.format(rubric=rubric, diff=diff)
    r = subprocess.run(["claude", "--print"], input=prompt, cwd=repo,
                       capture_output=True, text=True, timeout=LLM_TIMEOUT_S)
    out = r.stdout.strip()
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return {"_invalid": f"auditor returned no JSON: {out[:300]}"}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_invalid": f"auditor JSON unparseable: {e}"}
    findings = parsed.get("findings") or []
    justification = (parsed.get("no_findings_justification") or "").strip() \
        if isinstance(parsed.get("no_findings_justification"), str) else ""
    if not findings and not justification:
        return {"_invalid": "auditor returned neither findings nor a "
                            "no-findings justification (mandatory-findings rule)"}
    return parsed


def chain_append(log_path: Path, record: dict) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    prev = GENESIS
    seq = 0
    if log_path.exists():
        lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
        if lines:
            last = json.loads(lines[-1])
            prev = last["hash"]
            seq = last["seq"] + 1
    record = {"seq": seq, **record, "prev": prev}
    record["hash"] = hashlib.sha256(
        (prev + json.dumps(record, sort_keys=True)).encode()).hexdigest()
    with log_path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def verify_chain(log_path: Path) -> tuple[bool, str]:
    if not log_path.exists():
        return True, "no log yet (0 records)"
    prev = GENESIS
    n = 0
    for i, ln in enumerate(l for l in log_path.read_text().splitlines() if l.strip()):
        rec = json.loads(ln)
        claimed = rec.pop("hash")
        expect = hashlib.sha256(
            (prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest()
        if rec.get("prev") != prev or claimed != expect:
            return False, f"chain BROKEN at seq {rec.get('seq', i)}: record altered or reordered"
        prev = claimed
        n += 1
    return True, f"chain intact ({n} records)"


def cmd_audit(args: argparse.Namespace) -> int:
    repo = os.path.abspath(args.repo)
    t0 = time.time()
    diff = get_diff(repo, args.staged, args.range)
    if not diff.strip():
        print("audit-gate: empty diff, nothing to audit")
        return 0
    if len(diff) > MAX_DIFF_CHARS:
        print(f"audit-gate: FAIL — diff is {len(diff)} chars (cap {MAX_DIFF_CHARS}). "
              "Split the change; an audit nobody can read is not an audit.")
        return 1

    findings = scan_tripwires(diff)
    llm: dict = {}
    invalid = None
    if findings:
        # refuse-to-pass: tripwires fail the gate before any model call
        pass
    elif not args.no_llm:
        llm = run_llm_audit(diff, repo)
        invalid = llm.pop("_invalid", None)
        findings.extend(llm.get("findings") or [])

    blockers = [f for f in findings if f.get("severity") == "blocker"]
    majors = [f for f in findings if f.get("severity") == "major"]
    minors = [f for f in findings if f.get("severity") == "minor"]
    fail = bool(blockers) or bool(majors) or bool(invalid) \
        or (llm.get("verdict") == "fail")
    verdict = "FAIL" if fail else "PASS"

    rec = chain_append(Path(args.log), {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repo": repo,
        "mode": args.range or ("staged" if args.staged else "worktree"),
        "diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
        "verdict": verdict,
        "invalid_audit": invalid,
        "blockers": len(blockers), "majors": len(majors), "minors": len(minors),
        "deterministic_hits": sum(1 for f in findings if f.get("deterministic")),
        "rubric": llm.get("rubric"),
        "duration_s": round(time.time() - t0, 1),
    })

    if args.json:
        print(json.dumps({"verdict": verdict, "invalid_audit": invalid,
                          "findings": findings, "log_seq": rec["seq"]}, indent=2))
    else:
        print(f"audit-gate: {verdict}  "
              f"(blockers {len(blockers)}, majors {len(majors)}, minors {len(minors)}"
              f"{', INVALID AUDIT: ' + invalid if invalid else ''})")
        for f in findings:
            det = "tripwire" if f.get("deterministic") else f.get("severity", "?")
            print(f"  [{det}] {f.get('file', '?')}: {f.get('issue', '')}")
            if f.get("evidence"):
                print(f"      > {f['evidence']}")
        just = llm.get("no_findings_justification")
        if just and not findings:
            print(f"  no findings, auditor's justification: {just}")
        print(f"  logged as seq {rec['seq']} in {args.log}")
    return 1 if fail else 0


def cmd_verify_log(args: argparse.Namespace) -> int:
    ok, msg = verify_chain(Path(args.log))
    print(f"audit-gate: {msg}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="audit-gate", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit a diff")
    a.add_argument("--repo", default=".", help="repo path (default: cwd)")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="audit staged changes")
    g.add_argument("--range", help="audit a commit range, e.g. origin/main..HEAD")
    a.add_argument("--no-llm", action="store_true",
                   help="tripwires only (fast, deterministic)")
    a.add_argument("--log", default=str(DEFAULT_LOG))
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=cmd_audit)

    v = sub.add_parser("verify-log", help="verify the hash chain")
    v.add_argument("--log", default=str(DEFAULT_LOG))
    v.set_defaults(fn=cmd_verify_log)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
