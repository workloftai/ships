#!/usr/bin/env python3
"""cc-doctor — audit a Claude Code settings.json for the settings that fail quietly.

Most people run Claude Code with none of the high-leverage settings on, because
the defaults never complain. A few of those defaults cost you data, leak secrets
into context, or hand an agent more blast radius than you meant to. This script
points at your ~/.claude (and, optionally, a project's .claude) and tells you
which of a small, hand-checked set of settings are missing, why each one matters,
and the exact one-line fix.

Every key this tool checks is a real Claude Code setting, verified against the
shipped binary. It reads your config, it never writes to it: the fixes are
printed for you to paste. Nothing is sent anywhere.

Usage:
    cc-doctor.py                      # audit ~/.claude plus ./.claude if present
    cc-doctor.py --path /some/project # also fold in that project's .claude
    cc-doctor.py --json               # machine-readable report
    cc-doctor.py --quiet              # only show findings that need action

Exit codes:
    0  no high-severity findings
    1  at least one high-severity finding (usable as a CI gate)
    2  bad usage / could not read a settings file that exists

MIT licence. Steal what you want.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---- severities -------------------------------------------------------------

HIGH = "HIGH"      # silently loses data or leaks secrets — fix this
MEDIUM = "MEDIUM"  # meaningful blast-radius or cost — worth a look
LOW = "LOW"        # hygiene / preference — your call
INFO = "INFO"      # purely cosmetic

RANK = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}

# ---- settings loading -------------------------------------------------------
#
# Claude Code merges settings from several files. Later sources win. We fold
# them in the same precedence order so the audit sees the config the tool
# actually runs with:
#   1. ~/.claude/settings.json           (user, global)
#   2. <project>/.claude/settings.json   (project, shared/committed)
#   3. <project>/.claude/settings.local.json  (project, personal/gitignored)


def _read_json(p: Path) -> dict:
    """Read a JSON(-with-comments-tolerant) settings file. Returns {} if absent."""
    if not p.exists():
        return {}
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        print(f"cc-doctor: cannot read {p}: {e}", file=sys.stderr)
        sys.exit(2)
    # Tolerate a trailing-comma or // comment sloppiness by trying strict first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = _strip_jsonc(text)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as e:
            print(f"cc-doctor: {p} is not valid JSON: {e}", file=sys.stderr)
            sys.exit(2)


def _strip_jsonc(text: str) -> str:
    """Best-effort strip of // line comments and trailing commas. Not a parser."""
    out_lines = []
    for line in text.splitlines():
        # drop // comments that are not inside a string (naive but adequate here)
        in_str = False
        esc = False
        cut = None
        for i, ch in enumerate(line):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if ch == "/" and not in_str and i + 1 < len(line) and line[i + 1] == "/":
                cut = i
                break
        out_lines.append(line if cut is None else line[:cut])
    joined = "\n".join(out_lines)
    # remove trailing commas before } or ]
    import re

    return re.sub(r",(\s*[}\]])", r"\1", joined)


def _deep_merge(base: dict, over: dict) -> dict:
    """Shallow-recursive merge: dicts merge, everything else is replaced."""
    result = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_settings(project: Path | None) -> tuple[dict, list[str]]:
    """Return (merged settings, list of files that contributed)."""
    home = Path.home() / ".claude" / "settings.json"
    sources = [home]
    if project is not None:
        sources.append(project / ".claude" / "settings.json")
        sources.append(project / ".claude" / "settings.local.json")

    merged: dict = {}
    seen: list[str] = []
    for src in sources:
        data = _read_json(src)
        if data:
            merged = _deep_merge(merged, data)
            seen.append(str(src))
    return merged, seen


# ---- helpers over the merged settings --------------------------------------


def _permission_list(settings: dict, bucket: str) -> list[str]:
    perms = settings.get("permissions") or {}
    val = perms.get(bucket) or []
    return [str(x) for x in val] if isinstance(val, list) else []


def _env(settings: dict, key: str) -> str | None:
    env = settings.get("env") or {}
    if key in env:
        return str(env[key])
    # a real environment variable overrides / substitutes for the setting
    return os.environ.get(key)


def _rule_mentions(rules: list[str], needle: str) -> bool:
    return any(needle in r for r in rules)


# ---- the checks -------------------------------------------------------------
#
# Each check returns a finding dict, or None if the setting is already fine.
# Keeping them as small functions makes the ruleset easy to read and extend.


def check_cleanup_period(s: dict):
    val = s.get("cleanupPeriodDays")
    if isinstance(val, (int, float)) and val >= 90:
        return None
    current = "default (30 days)" if val is None else f"{val} days"
    return {
        "id": "cleanupPeriodDays",
        "severity": HIGH,
        "title": "Session history is on a short deletion timer",
        "current": current,
        "why": (
            "Claude Code deletes local chat transcripts older than cleanupPeriodDays, "
            "and the default is 30 days. It never warns you. If anything you rely on "
            "reads those transcripts (an audit trail, a metrics job, your own memory "
            "of what happened last month) it goes quietly missing."
        ),
        "fix": '"cleanupPeriodDays": 365',
        "note": "There is no 'keep forever' value; a large number is the way. Do not set 0 (it wipes history immediately).",
    }


def check_env_deny(s: dict):
    deny = _permission_list(s, "deny")
    if _rule_mentions(deny, ".env"):
        return None
    return {
        "id": "permissions.deny:.env",
        "severity": HIGH,
        "title": "Nothing stops the agent reading your .env",
        "current": "no deny rule mentions .env",
        "why": (
            "With no deny rule, an agent can read your .env and pull API keys and "
            "tokens straight into the context window, which then travels to the model "
            "and into your transcript. A deny rule is checked before any allow rule, "
            "so this is a hard floor."
        ),
        "fix": '"permissions": { "deny": ["Read(./.env)", "Read(./.env.*)"] }',
        "note": "Deny beats allow and ask, so no other rule can override it.",
    }


def check_git_push(s: dict):
    deny = _permission_list(s, "deny")
    ask = _permission_list(s, "ask")
    if _rule_mentions(deny, "git push") or _rule_mentions(ask, "git push"):
        return None
    return {
        "id": "permissions:git-push",
        "severity": MEDIUM,
        "title": "Publishing power is not fenced off",
        "current": "no deny/ask rule for git push",
        "why": (
            "An agent can commit and push in one motion. Committing locally is cheap "
            "to undo; pushing to a shared or production remote is not. Keeping push "
            "behind an explicit gate means the decision to publish stays with you."
        ),
        "fix": '"permissions": { "ask": ["Bash(git push:*)"] }',
        "note": "Use deny to forbid it outright, or ask to keep it one confirmation away.",
    }


def check_nonessential_traffic(s: dict):
    val = _env(s, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
    if val in ("1", "true", "True"):
        return None
    return {
        "id": "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "severity": LOW,
        "title": "Non-essential background traffic is on",
        "current": "unset",
        "why": (
            "By default Claude Code makes some background calls that are not part of "
            "the task: telemetry, error reports, update checks, the odd flavour call. "
            "One flag switches the lot off. Worth it if you run client work through "
            "the tool and want a quieter, more predictable footprint."
        ),
        "fix": '"env": { "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1" }',
        "note": "This single flag supersedes the several separate DISABLE_* flags older guides list.",
    }


def check_status_line(s: dict):
    if s.get("statusLine"):
        return None
    return {
        "id": "statusLine",
        "severity": LOW,
        "title": "No status line, so you cannot see context filling up",
        "current": "unset",
        "why": (
            "Without a status line you cannot see the context percentage, the model, "
            "or the running cost. That matters because output quality starts to slip "
            "well before the window is full, and you cannot compact early if you "
            "cannot see how full it is."
        ),
        "fix": '"statusLine": { "type": "command", "command": "<your status script>" }',
        "note": "Easiest path: run /statusline inside Claude Code and let it write this for you.",
    }


def check_coauthored(s: dict):
    # Opinion, not safety: only flag it, never insist.
    if s.get("includeCoAuthoredBy") is False:
        return None
    return {
        "id": "includeCoAuthoredBy",
        "severity": INFO,
        "title": "Commits carry a co-authored-by trailer",
        "current": "default (on)",
        "why": (
            "Every commit gets a co-authored-by trailer crediting the assistant. "
            "Plenty of teams are happy with that. Some do not want AI attribution on "
            "every commit in the history. Purely your call."
        ),
        "fix": '"includeCoAuthoredBy": false',
        "note": "This is a preference, not a problem. Left on is a perfectly good answer.",
    }


CHECKS = [
    check_cleanup_period,
    check_env_deny,
    check_git_push,
    check_nonessential_traffic,
    check_status_line,
    check_coauthored,
]


# ---- rendering --------------------------------------------------------------

C = {
    HIGH: "\033[31m", MEDIUM: "\033[33m", LOW: "\033[36m",
    INFO: "\033[90m", "ok": "\033[32m", "bold": "\033[1m", "off": "\033[0m",
}


def _c(key: str, text: str, use_colour: bool) -> str:
    return f"{C[key]}{text}{C['off']}" if use_colour else text


def render_human(findings, sources, total_checks, quiet, use_colour):
    passed = total_checks - len(findings)
    print()
    print(_c("bold", "cc-doctor — Claude Code settings audit", use_colour))
    if sources:
        print("read: " + ", ".join(sources))
    else:
        print("read: no settings.json found (auditing defaults)")
    print(f"{passed}/{total_checks} checks clean, {len(findings)} to look at")
    print()

    if not findings:
        print(_c("ok", "Nothing to fix. Your config is on the good defaults.", use_colour))
        print()
        return

    for f in findings:
        sev = f["severity"]
        tag = _c(sev, f"[{sev}]", use_colour)
        print(f"{tag} {_c('bold', f['title'], use_colour)}")
        print(f"  setting : {f['id']}")
        print(f"  now     : {f['current']}")
        print(f"  why     : {f['why']}")
        print(f"  fix     : {_c('ok', f['fix'], use_colour)}")
        if f.get("note"):
            print(f"  note    : {f['note']}")
        print()

    if not quiet:
        print("Paste the fixes into ~/.claude/settings.json. Nothing was changed for you.")
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit Claude Code settings for the ones that fail quietly.")
    ap.add_argument("--path", type=str, default=None,
                    help="a project directory whose .claude settings to fold in (defaults to cwd if it has .claude)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="only show findings, drop the footer")
    ap.add_argument("--no-colour", action="store_true", help="disable ANSI colour")
    args = ap.parse_args(argv)

    project = None
    if args.path:
        project = Path(args.path).expanduser()
    elif (Path.cwd() / ".claude").exists():
        project = Path.cwd()

    settings, sources = load_settings(project)

    findings = [f for f in (chk(settings) for chk in CHECKS) if f]
    findings.sort(key=lambda f: RANK[f["severity"]])

    if args.json:
        print(json.dumps({
            "sources": sources,
            "checks": len(CHECKS),
            "findings": findings,
        }, indent=2))
    else:
        use_colour = sys.stdout.isatty() and not args.no_colour
        render_human(findings, sources, len(CHECKS), args.quiet, use_colour)

    return 1 if any(f["severity"] == HIGH for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
