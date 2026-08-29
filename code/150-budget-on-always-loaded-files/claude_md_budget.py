#!/usr/bin/env python3
"""
claude_md_budget.py — warn when an always-loaded context file blows its budget.

CLAUDE.md, AGENTS.md and the memory MEMORY.md index are loaded into EVERY
session's context. They only ever grow: a rule here, a note there, and one day
you are paying a few hundred tokens of tax on every single turn for guidance the
model half-reads. Nothing tells you it happened, because each edit looked small.

This is the thing that tells you. As a PostToolUse hook it fires after a Write or
Edit to a watched context file, measures it against a token budget, and when it
is over it surfaces a warning naming the largest sections to move out into a
rules directory. It never blocks the edit and never moves anything: it is a
gauge, not a gate.

It also runs as a plain CLI so you can audit a file on demand:

    python3 claude_md_budget.py <file>            # report
    python3 claude_md_budget.py <file> --apply     # extract the biggest section

Fails open: any parse/IO error exits 0 so a broken gauge never disrupts a write.
"""

import json
import os
import re
import sys

# Basenames that are loaded into context every session. Add your own.
WATCHED = {"CLAUDE.md", "AGENTS.md", "MEMORY.md"}

# Token budget per watched file (rough estimate: 1 token ~= 4 chars). Override
# with the env var, e.g. CLAUDE_MD_BUDGET_TOKENS=2000.
BUDGET_TOKENS = int(os.environ.get("CLAUDE_MD_BUDGET_TOKENS", "1500"))

HEADER = re.compile(r"^(#{1,6})\s+(.*)$")


def est_tokens(text):
    return len(text) // 4


def split_sections(text):
    """Return [(header, body_including_header, tokens)] split on markdown
    headers. Text before the first header is a section titled '(preamble)'."""
    lines = text.splitlines(keepends=True)
    sections, cur_head, cur = [], "(preamble)", []
    for ln in lines:
        m = HEADER.match(ln.rstrip("\n"))
        if m:
            if cur:
                blob = "".join(cur)
                sections.append((cur_head, blob, est_tokens(blob)))
            cur_head = m.group(2).strip() or m.group(1)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blob = "".join(cur)
        sections.append((cur_head, blob, est_tokens(blob)))
    return sections


def report(path, text):
    total = est_tokens(text)
    over = total - BUDGET_TOKENS
    secs = sorted(split_sections(text), key=lambda s: -s[2])
    lines = [
        f"context-budget: {os.path.basename(path)} is ~{total} tokens, "
        f"budget {BUDGET_TOKENS} ({'OVER by ' + str(over) if over > 0 else 'ok, ' + str(-over) + ' to spare'}).",
    ]
    if over > 0:
        lines.append("Largest sections (move the top ones into a rules file to "
                     "reclaim per-session tokens):")
        for head, _blob, tok in secs[:4]:
            lines.append(f"  ~{tok} tok  {head}")
        lines.append("Extract with:  python3 "
                     f"{os.path.abspath(__file__)} {path} --apply")
    return "\n".join(lines), over


def apply_extract(path, text):
    """Move the single largest section into <dir>/.claude/rules/<slug>.md and
    leave a one-line pointer behind. Non-destructive elsewhere; writes a .bak."""
    secs = split_sections(text)
    if not secs:
        return "nothing to extract"
    head, blob, tok = max(secs, key=lambda s: s[2])
    if head == "(preamble)":
        # do not gut the top of the file; pick the largest real section
        real = [s for s in secs if s[0] != "(preamble)"]
        if not real:
            return "only a preamble, nothing safe to extract"
        head, blob, tok = max(real, key=lambda s: s[2])
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(path)),
                             ".claude", "rules")
    os.makedirs(rules_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", head.lower()).strip("-")[:48] or "section"
    dest = os.path.join(rules_dir, slug + ".md")
    with open(path + ".bak", "w") as f:
        f.write(text)
    with open(dest, "w") as f:
        f.write(blob)
    pointer = f"\n> Moved to `.claude/rules/{slug}.md` (~{tok} tok) to keep this file lean.\n"
    new_text = text.replace(blob, pointer)
    with open(path, "w") as f:
        f.write(new_text)
    return (f"extracted '{head}' (~{tok} tok) -> {dest}\n"
            f"backup at {path}.bak; left a pointer in place.")


# --- hook mode ---------------------------------------------------------------

def hook_main(data):
    tool = data.get("tool_name")
    if tool not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ""
    if os.path.basename(fp) not in WATCHED:
        sys.exit(0)
    try:
        with open(fp) as f:            # PostToolUse: read the file as written
            text = f.read()
    except Exception:
        sys.exit(0)
    msg, over = report(fp, text)
    if over > 0:
        sys.stderr.write(msg + "\n")
        sys.exit(2)                    # PostToolUse: surfaces msg, does NOT block
    sys.exit(0)


def main():
    # CLI mode if a path arg is given; hook mode if JSON arrives on stdin.
    args = [a for a in sys.argv[1:]]
    if args and os.path.exists(args[0]):
        path = args[0]
        text = open(path).read()
        if "--apply" in args:
            print(apply_extract(path, text))
        else:
            print(report(path, text)[0])
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    hook_main(data)


if __name__ == "__main__":
    main()
