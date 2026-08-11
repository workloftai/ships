#!/usr/bin/env python3
"""
skillscan - a supply-chain scanner for agent skills.

An agent "skill" (a SKILL.md plus whatever scripts sit beside it) is
unreviewed third-party code that runs with your agent's full credentials:
its SSH keys, its cloud tokens, its shell. Installing one from a public
registry is the same trust decision as `curl | bash`, except the payload
can also be plain-English instructions to your model.

skillscan treats every skill as hostile until proven otherwise. It walks a
folder, finds each skill, and scans the SKILL.md and its sibling scripts for
the patterns a credential-stealer actually uses: reading secret paths,
posting them to an outside host, editing its own files to survive deletion,
obfuscated payloads, and instructions that try to override the agent.

No dependencies. One file. Python 3.8+.

    skillscan.py scan <path>        # scan a folder of skills
    skillscan.py scan <path> --json # machine-readable
    skillscan.py scan <path> --min block   # only print BLOCK skills

Exit code is 2 if any skill scores BLOCK, so it works as a pre-install gate
or a CI step. A per-skill `.skillscan-allow` file waives known false
positives (see README).
"""
import argparse
import json
import os
import re
import sys

# ---- severity weights -------------------------------------------------------
HIGH, MED, LOW = 5, 2, 1
VERDICTS = ("CLEAN", "REVIEW", "BLOCK")


def verdict_for(score, has_high):
    # any single HIGH finding is enough to block: one exfil line is one too many
    if has_high or score >= 5:
        return "BLOCK"
    if score >= 2:
        return "REVIEW"
    return "CLEAN"


# ---- the rules --------------------------------------------------------------
# Each rule: id, human label, severity, compiled regex, and whether it only
# applies to executable script files (not prose SKILL.md), to cut false hits.
def _r(pattern, flags=re.I):
    return re.compile(pattern, flags)


RULES = [
    # ---- credential access ----
    dict(id="cred.ssh_key", label="reads an SSH private key", sev=HIGH, scripts_only=False,
         rx=_r(r"(?:\.ssh/|/ssh/)?id_(?:rsa|ed25519|ecdsa|dsa)\b|~/\.ssh\b|/\.ssh/")),
    dict(id="cred.dotenv", label="reads a .env / secrets file", sev=HIGH, scripts_only=True,
         rx=_r(r"\b(?:cat|open|read|load_dotenv|source)\b[^\n]{0,40}\.env\b|/\.env\b")),
    dict(id="cred.cloud", label="reads cloud credentials", sev=HIGH, scripts_only=False,
         rx=_r(r"~?/\.aws/credentials|~?/\.config/gcloud|~?/\.config/gh/|/\.kube/config|/\.docker/config\.json")),
    dict(id="cred.env_secret", label="reads a secret from the environment", sev=MED, scripts_only=True,
         rx=_r(r"(?:os\.environ|getenv|process\.env|ENV\[)[^\n]{0,30}(?:TOKEN|SECRET|API[_-]?KEY|PASSWORD|PRIVATE[_-]?KEY)")),
    dict(id="cred.system", label="reads system credential stores", sev=HIGH, scripts_only=False,
         rx=_r(r"/etc/shadow|/etc/passwd\b|Login Data|Cookies\b.*(?:Chrome|Firefox|Safari)|keychain")),
    # ---- exfiltration ----
    dict(id="exfil.post", label="posts data to an external host", sev=HIGH, scripts_only=True,
         rx=_r(r"(?:requests\.post|urllib\.request|http\.client|fetch\(|axios\.|curl\s+[^\n]*-d|wget\s+[^\n]*--post)")),
    dict(id="exfil.pipe_net", label="pipes output straight to the network", sev=HIGH, scripts_only=True,
         rx=_r(r"\|\s*(?:curl|wget|nc|ncat|netcat)\b|>\s*/dev/tcp/")),
    dict(id="exfil.dns", label="looks like DNS-tunnel exfiltration", sev=MED, scripts_only=True,
         rx=_r(r"(?:dig|nslookup|host)\s+[^\n]*\$\(|\.oast\.|\.burpcollaborator\.|\.interact\.sh")),
    # ---- self-modification / persistence ----
    dict(id="persist.self_edit", label="edits its own skill files", sev=HIGH, scripts_only=False,
         rx=_r(r"SKILL\.md[^\n]{0,40}(?:>|write|open\([^\n]*['\"][wa]|sed\s+-i|tee\b)|(?:rewrite|overwrite|regenerate)[^\n]{0,20}(?:this|its own|the)\s+(?:skill|prompt|instructions)")),
    dict(id="persist.survive", label="claims to survive deletion / removal", sev=HIGH, scripts_only=False,
         rx=_r(r"survive (?:deletion|removal|uninstall)|re-?install (?:itself|yourself)|restore (?:itself|yourself) if (?:deleted|removed)|persist(?:ence)? across")),
    dict(id="persist.rc", label="writes to a shell startup file", sev=HIGH, scripts_only=True,
         rx=_r(r">>?\s*~?/?\.(?:bashrc|zshrc|profile|bash_profile)|/etc/profile\.d/")),
    dict(id="persist.schedule", label="installs a cron / systemd / launchd job", sev=MED, scripts_only=True,
         rx=_r(r"\bcrontab\b|/etc/cron|systemctl\s+(?:enable|--user)|launchctl\s+load|LaunchAgents")),
    # ---- obfuscation ----
    dict(id="obf.base64", label="contains a large base64 / hex blob", sev=MED, scripts_only=False,
         rx=_r(r"[A-Za-z0-9+/]{120,}={0,2}|(?:\\x[0-9a-f]{2}){12,}")),
    dict(id="obf.eval", label="evaluates code from a string", sev=HIGH, scripts_only=True,
         rx=_r(r"\beval\s*\(|\bexec\s*\(|Function\s*\(\s*['\"]|new Function|base64\.b64decode[^\n]{0,40}(?:exec|eval)|atob\s*\(")),
    # ---- destructive ----
    dict(id="destr.rm", label="destructive filesystem command", sev=MED, scripts_only=True,
         rx=_r(r"\brm\s+-[rf]{1,2}[a-z]*\s+(?:/|~|\$)|\bmkfs\b|\bdd\s+if=|:\(\)\{.*\|.*&\};:")),
    dict(id="destr.forcepush", label="force-pushes or rewrites git history", sev=LOW, scripts_only=True,
         rx=_r(r"git\s+push[^\n]*--force(?!-with-lease)|git\s+push[^\n]*\s-f\b|git\s+reset\s+--hard\s+[^\n]*origin")),
    dict(id="destr.chmod", label="opens permissions wide (chmod 777)", sev=LOW, scripts_only=True,
         rx=_r(r"chmod\s+(?:-R\s+)?0?777\b")),
    # ---- prompt injection / instruction override (prose payloads) ----
    dict(id="inject.override", label="tries to override the agent's instructions", sev=MED, scripts_only=False,
         rx=_r(r"ignore (?:all |any )?(?:previous|prior|above) (?:instructions|prompts|rules)|disregard (?:the|all|your) (?:system|previous)|you are now (?:a|an|in) |do not (?:tell|mention to|inform) the user")),
    dict(id="inject.hidden", label="hides instructions from the user", sev=MED, scripts_only=False,
         rx=_r(r"without (?:telling|informing|alerting) the user|silently (?:send|upload|exfil|copy)|do this in the background and")),
]


# ---- file discovery ---------------------------------------------------------
SCRIPT_EXT = (".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1")
TEXT_EXT = SCRIPT_EXT + (".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".toml")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def is_script(path):
    return path.lower().endswith(SCRIPT_EXT)


# languages inside a ```fence that mean "the agent is told to run this"
EXEC_FENCE = re.compile(r"^\s*(?:```|~~~)\s*(bash|sh|shell|console|zsh|python|py|javascript|js|node|ruby|rb|perl)\b", re.I)
FENCE_CLOSE = re.compile(r"^\s*(?:```|~~~)\s*$")


def exec_block_lines(lines):
    """Line numbers (1-indexed) inside fenced code blocks tagged as a shell or
    scripting language in a markdown file. A malicious SKILL.md hides its
    payload as a 'run this' block, so those lines get the script rules too."""
    inside, marked = False, set()
    for i, line in enumerate(lines, 1):
        if not inside and EXEC_FENCE.match(line):
            inside = True
            continue
        if inside and FENCE_CLOSE.match(line):
            inside = False
            continue
        if inside:
            marked.add(i)
    return marked


def find_skills(root):
    """A skill = a directory containing a SKILL.md (any case). Fallback: a
    standalone *.md that declares skill frontmatter (name:/description:)."""
    skills = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        lower = {f.lower(): f for f in filenames}
        if "skill.md" in lower:
            skills.append(dict(name=os.path.basename(dirpath.rstrip("/")) or dirpath,
                               root=dirpath,
                               manifest=os.path.join(dirpath, lower["skill.md"])))
            # don't descend into a skill's own subtree as separate skills
            dirnames[:] = [d for d in dirnames if not os.path.isfile(
                os.path.join(dirpath, d, "SKILL.md"))]
    if skills:
        return skills
    # fallback: flat single-file skills (e.g. commands/*.md)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.lower().endswith((".md", ".markdown")):
                p = os.path.join(dirpath, f)
                try:
                    head = open(p, encoding="utf-8", errors="replace").read(400)
                except OSError:
                    continue
                if re.search(r"^\s*name:\s*\S", head, re.M) and re.search(r"description:\s*\S", head, re.M):
                    skills.append(dict(name=os.path.splitext(f)[0], root=dirpath, manifest=p))
    return skills


def skill_files(skill):
    """Every text file that belongs to this skill."""
    manifest = skill["manifest"]
    if os.path.isdir(skill["root"]) and os.path.basename(manifest).lower() == "skill.md":
        out = []
        for dirpath, dirnames, filenames in os.walk(skill["root"]):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f.lower().endswith(TEXT_EXT):
                    out.append(os.path.join(dirpath, f))
        return out
    return [manifest]


def load_allow(skill_root):
    """A `.skillscan-allow` file: one rule id per line waives that rule for
    this skill. Blank lines and #comments ignored."""
    allow = set()
    p = os.path.join(skill_root, ".skillscan-allow")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.split("#", 1)[0].strip()
            if line:
                allow.add(line)
    return allow


# ---- scanning ---------------------------------------------------------------
def scan_file(path, allow):
    findings = []
    script = is_script(path)
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return findings
    lines = text.splitlines()
    # in a markdown file, fenced shell/python blocks are executable payloads
    is_md = path.lower().endswith((".md", ".markdown"))
    fenced = exec_block_lines(lines) if is_md else set()
    for rule in RULES:
        if rule["id"] in allow:
            continue
        for i, line in enumerate(lines, 1):
            # script rules fire in real scripts, and inside fenced code blocks
            if rule["scripts_only"] and not (script or i in fenced):
                continue
            if rule["rx"].search(line):
                findings.append(dict(rule=rule["id"], label=rule["label"], sev=rule["sev"],
                                     file=path, line=i, text=line.strip()[:160]))
                break  # one hit per rule per file is enough signal
    return findings


def scan_skill(skill):
    allow = load_allow(skill["root"])
    findings = []
    for f in skill_files(skill):
        findings.extend(scan_file(f, allow))
    score = sum(f["sev"] for f in findings)
    has_high = any(f["sev"] == HIGH for f in findings)
    return dict(name=skill["name"], root=skill["root"],
                verdict=verdict_for(score, has_high), score=score, findings=findings)


# ---- output -----------------------------------------------------------------
COLOR = dict(BLOCK="\033[31m", REVIEW="\033[33m", CLEAN="\033[32m", off="\033[0m")


def paint(v):
    if not sys.stdout.isatty():
        return v
    return f"{COLOR.get(v,'')}{v}{COLOR['off']}"


def print_report(results, min_verdict):
    order = {v: i for i, v in enumerate(VERDICTS)}
    floor = order.get(min_verdict.upper(), 0)
    shown = [r for r in results if order[r["verdict"]] >= floor]
    for r in sorted(results, key=lambda r: (-order[r["verdict"]], r["name"])):
        if order[r["verdict"]] < floor:
            continue
        print(f"\n{paint(r['verdict']):>6}  {r['name']}  (score {r['score']})")
        for f in sorted(r["findings"], key=lambda f: -f["sev"]):
            sev = {HIGH: "HIGH", MED: "MED", LOW: "LOW"}[f["sev"]]
            rel = os.path.relpath(f["file"], r["root"])
            print(f"         [{sev:>4}] {f['label']}")
            print(f"                {rel}:{f['line']}  {f['text']}")
    n = {v: sum(1 for r in results if r["verdict"] == v) for v in VERDICTS}
    print(f"\n{'-'*60}")
    print(f"scanned {len(results)} skill(s): "
          f"{paint('BLOCK')} {n['BLOCK']}  {paint('REVIEW')} {n['REVIEW']}  {paint('CLEAN')} {n['CLEAN']}")
    if not shown:
        print("(nothing at or above the --min threshold)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Supply-chain scanner for agent skills.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scan", help="scan a folder of skills")
    sp.add_argument("path", help="folder to scan (walks for SKILL.md)")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.add_argument("--min", default="clean", choices=[v.lower() for v in VERDICTS],
                    help="only print skills at or above this verdict")
    args = ap.parse_args(argv)

    if not os.path.exists(args.path):
        print(f"skillscan: no such path: {args.path}", file=sys.stderr)
        return 3

    skills = find_skills(args.path)
    results = [scan_skill(s) for s in skills]

    if args.json:
        print(json.dumps(dict(scanned=len(results), results=results), indent=2))
    else:
        if not results:
            print(f"skillscan: found no skills under {args.path} "
                  f"(looked for SKILL.md, then *.md with name/description frontmatter)")
        else:
            print_report(results, args.min)

    return 2 if any(r["verdict"] == "BLOCK" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
