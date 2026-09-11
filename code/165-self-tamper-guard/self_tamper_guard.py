#!/usr/bin/env python3
"""self_tamper_guard: a PreToolUse hook that stops an agent disabling its own guardrails.

The failure mode is real. CVE-2026-82533 (DeepSeek Harness) let an AI coding agent
turn off its own sandbox. Once an agent can edit the thing that constrains it, the
constraint is decorative. A firewall the agent can flush, a hook the agent can
delete, a settings file the agent can rewrite: none of those are controls, they are
suggestions.

So this guards the guardrail surface itself. It sits in front of every tool call and
refuses the ones that would tamper with the controls:

  * Edit / Write / NotebookEdit whose target is settings.json, anything under
    .claude/hooks/, or this guard's own config  ->  BLOCKED.
  * Bash that deletes, moves, chmods, truncates or redirects into any of those
    protected paths  ->  BLOCKED. (Reading them with cat/grep is fine.)
  * Optional egress mode (SELF_TAMPER_EGRESS=enforce): Bash that reaches a host not
    on the allowlist via curl/wget/nc/scp/ssh/rsync  ->  BLOCKED.

Design, deliberately:
  * stdin = the PreToolUse JSON; exit 0 = allow, exit 2 = block (+ a specific reason
    on stderr). Same contract as the other hooks in this repo.
  * NO in-band bypass for the protected surface. A magic "# ok" comment the agent can
    append would defeat the entire point (the agent could wave the guard away). The
    only way past is out of band: a human sets SELF_TAMPER_UNLOCK=1 in the parent
    shell before launching, or stops the agent and edits the file themselves. That is
    the CVE lesson made concrete: the off switch must live where the agent cannot reach.
  * Fails OPEN on parse errors only. A malformed hook event should not brick the
    session. But a well-formed event that targets a protected path fails CLOSED.
  * Honest limit: this runs inside the same process tree as the agent, so a
    sufficiently determined agent could in principle set the unlock var itself. The
    real fix is the harness enforcing this in a separate trust domain. This is the
    pragmatic 90%: it stops the accidental and the prompt-injected, which is most of it.

Dependency-free: stdlib only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

# --- protected guardrail surface -------------------------------------------------
# Path fragments that must never be mutated by a tool call. Matched against the
# normalised absolute target path. Add your own in protected.txt (one per line).
DEFAULT_PROTECTED = [
    "/.claude/settings.json",
    "/.claude/settings.local.json",
    "/.claude/hooks/",          # every hook, including this one
]


def load_list(name, default):
    path = os.path.join(HERE, name)
    items = list(default)
    try:
        with open(path) as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    items.append(line)
    except FileNotFoundError:
        pass
    return items


def protected_fragments():
    frags = load_list("protected.txt", DEFAULT_PROTECTED)
    # always protect this guard's own directory, whatever it is called
    frags.append(HERE.rstrip("/") + "/")
    return frags


def egress_allowlist():
    # suffix-matched hostnames allowed to be reached in enforce mode
    default = [
        "anthropic.com", "openai.com", "telegram.org", "supabase.co",
        "vercel.app", "vercel.com", "github.com", "githubusercontent.com",
        "gitlab.com", "pypi.org", "pythonhosted.org", "npmjs.org",
        "googleapis.com", "together.xyz", "perplexity.ai",
    ]
    return load_list("allowlist.txt", default)


def norm(path):
    if not path:
        return ""
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(os.getcwd(), p)
    return os.path.normpath(p)


def hits_protected(path, frags):
    n = norm(path)
    for fr in frags:
        f = os.path.expanduser(fr)
        if f in n or f in (n + "/"):
            return fr
    return None


# --- bash inspection -------------------------------------------------------------
MUTATE = re.compile(
    r"(\brm\b|\bmv\b|\bcp\b|\bchmod\b|\bchown\b|\btee\b|\btruncate\b|\bln\b|"
    r"\binstall\b|\bshred\b|\bsed\b[^\n]*\s-i|>{1,2}(?!&))",
    re.I,
)
URL_HOST = re.compile(r"https?://([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})", re.I)
NET_HOST = re.compile(
    r"\b(?:scp|ssh|sftp|rsync)\b[^\n|]*?\b([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})",
    re.I,
)
NET_TOOL = re.compile(r"\b(curl|wget|nc|ncat|scp|ssh|sftp|rsync)\b", re.I)


def bash_protected_hit(cmd, frags):
    """A protected path being written, moved, deleted or redirected into."""
    if not MUTATE.search(cmd):
        return None
    for fr in frags:
        f = os.path.expanduser(fr).rstrip("/")
        # match the fragment as it would appear literally in a command
        for token in (fr, f, fr.replace(HOME, "~"), f.replace(HOME, "~")):
            if token and token in cmd:
                return fr
    return None


def bash_egress_hit(cmd, allow):
    if not NET_TOOL.search(cmd):
        return None
    hosts = set(h.lower() for h in URL_HOST.findall(cmd))
    hosts |= set(h.lower() for h in NET_HOST.findall(cmd))
    for h in hosts:
        if h in ("localhost",) or h.startswith("127."):
            continue
        if not any(h == a or h.endswith("." + a) for a in allow):
            return h
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail open on malformed events only

    if os.environ.get("SELF_TAMPER_UNLOCK") == "1":
        sys.exit(0)  # human break-glass, set out of band

    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    frags = protected_fragments()

    if tool in ("Edit", "Write", "NotebookEdit"):
        target = ti.get("file_path") or ti.get("notebook_path") or ""
        fr = hits_protected(target, frags)
        if fr:
            sys.stderr.write(
                "BLOCKED by self_tamper_guard: this "
                f"{tool} targets a protected guardrail file ({fr}).\n"
                "An agent that can edit its own controls has no controls. If this is a\n"
                "genuine, intended change, make it as the human operator or relaunch\n"
                "with SELF_TAMPER_UNLOCK=1. There is no in-band override on purpose.\n"
            )
            sys.exit(2)
        sys.exit(0)

    if tool == "Bash":
        cmd = ti.get("command") or ""
        fr = bash_protected_hit(cmd, frags)
        if fr:
            sys.stderr.write(
                "BLOCKED by self_tamper_guard: this Bash command mutates a protected\n"
                f"guardrail path ({fr}). Reading it is fine, rewriting or deleting it is\n"
                "not. Relaunch with SELF_TAMPER_UNLOCK=1 to make an intended change.\n"
            )
            sys.exit(2)
        if os.environ.get("SELF_TAMPER_EGRESS") == "enforce":
            host = bash_egress_hit(cmd, egress_allowlist())
            if host:
                sys.stderr.write(
                    "BLOCKED by self_tamper_guard (egress enforce): this command reaches\n"
                    f"'{host}', which is not on the egress allowlist. Add it to allowlist.txt\n"
                    "if it is meant to be reachable.\n"
                )
                sys.exit(2)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
