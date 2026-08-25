#!/usr/bin/env python3
"""context-tax — measure where a Claude Code setup's always-on token budget goes.

The argument doing the rounds is whether AGENTS.md / CLAUDE.md files earn their
token cost. That argument is usually aimed at the wrong file. In a real setup the
always-on tax is not one file, it is a stack of injections that ride into every
single session before you type a word: the CLAUDE.md chain, the memory index, and
- the part nobody measures - whatever your SessionStart hooks print.

This tool reads them all, runs the hooks, and prints a table ranked by weight so
you can see where the budget actually goes and decide what to cut. It is
stdlib-only and read-only (it never writes to your project). The one thing it
executes is your SessionStart hook commands, because their output is the hidden
tax and there is no other way to weigh it; pass --skip-hooks to turn that off.

Token counts are a chars/4 estimate unless tiktoken is importable, in which case
it is used automatically. The estimate is close enough to rank; ranking is the point.

Usage:
    python3 context_tax.py [PROJECT_DIR] [--skip-hooks] [--json]

PROJECT_DIR defaults to the current directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --- token counting -----------------------------------------------------------

def _make_counter():
    """Return (count_fn, method_name). Prefer a real tokenizer, fall back to chars/4."""
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken/cl100k_base"
    except Exception:
        return (lambda s: (len(s) + 3) // 4), "chars/4 estimate"


# --- categorisation -----------------------------------------------------------
# The whole point of ranking is weight x read-probability. Weight we measure.
# Read-probability we can't measure, so we bucket by role and let the human judge:
# identity/rules are load-bearing every turn; reference is load-on-demand material
# that happens to be pinned; backlog is the classic high-weight, low-read offender.

CATEGORY_RULES = [
    ("backlog",   re.compile(r"loop.?board|backlog|queue|research.?board|todo", re.I)),
    ("memory",    re.compile(r"memory|MEMORY\.md|hindsight|MOC", re.I)),
    ("routing",   re.compile(r"sop.?routing|fleet.?registry|registry|routing", re.I)),
    ("rules",     re.compile(r"AGENTS\.md|CLAUDE\.md", re.I)),
]

def categorise(label: str) -> str:
    for name, rx in CATEGORY_RULES:
        if rx.search(label):
            return name
    return "other"


@dataclass
class Source:
    label: str
    kind: str          # "file" or "hook"
    category: str
    tokens: int
    detail: str = ""


# --- file discovery -----------------------------------------------------------

IMPORT_RE = re.compile(r"^@([^\s]+)\s*$", re.M)

def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def resolve_context_files(project: Path) -> list[Path]:
    """CLAUDE.md / AGENTS.md in the project chain + user home, following one level
    of @imports (Claude Code's import syntax)."""
    seen: dict[Path, None] = {}
    candidates: list[Path] = []

    # project dir and its parents up to home, plus ~/.claude and home itself
    chain = [project, *project.parents]
    home = Path.home()
    for d in chain:
        for name in ("CLAUDE.md", "AGENTS.md"):
            candidates.append(d / name)
        if d == home:
            break
    candidates.append(home / ".claude" / "CLAUDE.md")

    resolved: list[Path] = []
    for c in candidates:
        if c.is_file() and c.resolve() not in seen:
            seen[c.resolve()] = None
            resolved.append(c)
            # follow one level of @imports, relative to the file's dir
            for m in IMPORT_RE.finditer(_read(c)):
                imp = (c.parent / m.group(1)).expanduser()
                if imp.is_file() and imp.resolve() not in seen:
                    seen[imp.resolve()] = None
                    resolved.append(imp)
    return resolved


def find_memory_index(project: Path) -> Path | None:
    """The always-on memory index, if the auto-memory layout is present."""
    slug = "-" + str(project.resolve()).strip("/").replace("/", "-")
    p = Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"
    return p if p.is_file() else None


# --- hook discovery + execution ----------------------------------------------

def load_settings(project: Path) -> list[dict]:
    """SessionStart hook entries from user + project settings.json (both layers)."""
    out: list[dict] = []
    for sp in (Path.home() / ".claude" / "settings.json",
               project / ".claude" / "settings.json",
               project / ".claude" / "settings.local.json"):
        if not sp.is_file():
            continue
        try:
            data = json.loads(_read(sp))
        except Exception:
            continue
        for entry in (data.get("hooks", {}) or {}).get("SessionStart", []) or []:
            for h in entry.get("hooks", []) or []:
                if h.get("type") == "command" and h.get("command"):
                    out.append({"command": h["command"], "source": str(sp)})
    return out


def run_hook(cmd: str, project: Path, timeout: int) -> tuple[str, str]:
    """Run a SessionStart hook, return (stdout, error). Read-only best effort."""
    try:
        # Decode defensively: hook output routinely carries emoji and box-drawing
        # bytes, and a strict decode zeroes out the very source the audit is about.
        r = subprocess.run(cmd, shell=True, cwd=str(project), capture_output=True,
                           timeout=timeout)
        return r.stdout.decode("utf-8", errors="replace"), ""
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s"
    except Exception as e:  # noqa: BLE001
        return "", str(e)


# --- audit --------------------------------------------------------------------

def audit(project: Path, skip_hooks: bool, timeout: int) -> tuple[list[Source], str]:
    count, method = _make_counter()
    sources: list[Source] = []

    for f in resolve_context_files(project):
        txt = _read(f)
        label = _shorten(f)
        sources.append(Source(label, "file", categorise(f.name + " " + label),
                              count(txt), "always-on file"))

    mem = find_memory_index(project)
    if mem:
        sources.append(Source("MEMORY.md (memory index)", "file", "memory",
                              count(_read(mem)), "loaded every session"))

    if not skip_hooks:
        for hk in load_settings(project):
            out, err = run_hook(hk["command"], project, timeout)
            label = "hook: " + _cmd_label(hk["command"])
            if err:
                sources.append(Source(label, "hook", categorise(hk["command"]), 0,
                                      f"NOT MEASURED ({err})"))
            else:
                sources.append(Source(label, "hook", categorise(hk["command"]),
                                      count(out), "SessionStart injection"))

    sources.sort(key=lambda s: s.tokens, reverse=True)
    return sources, method


def _shorten(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)

def _cmd_label(cmd: str) -> str:
    # last path-ish token, trimmed, so the table reads cleanly
    tok = cmd.strip().split()
    for t in reversed(tok):
        if "/" in t or t.endswith((".sh", ".py")):
            return Path(t).name
    return (tok[0] if tok else cmd)[:40]


# --- reporting ----------------------------------------------------------------

def render(sources: list[Source], method: str) -> str:
    total = sum(s.tokens for s in sources) or 1
    lines = []
    lines.append("context-tax - always-on token budget per session")
    lines.append(f"(token counts: {method})")
    lines.append("")
    lines.append(f"{'source':<40}{'category':<10}{'tokens':>8}{'share':>8}")
    lines.append("-" * 66)
    for s in sources:
        share = f"{100*s.tokens/total:4.1f}%"
        note = "" if s.tokens else "  <- " + s.detail
        lines.append(f"{s.label[:39]:<40}{s.category:<10}{s.tokens:>8}{share:>8}{note}")
    lines.append("-" * 66)
    lines.append(f"{'TOTAL always-on tax':<50}{sum(s.tokens for s in sources):>8}")
    lines.append("")

    # by category
    cats: dict[str, int] = {}
    for s in sources:
        cats[s.category] = cats.get(s.category, 0) + s.tokens
    lines.append("by category:")
    for c, t in sorted(cats.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"  {c:<12}{t:>8}{100*t/total:>7.1f}%")
    lines.append("")

    # the verdict: heaviest single source, and the biggest non-rules line
    heaviest = sources[0] if sources else None
    if heaviest:
        lines.append(f"heaviest single source: {heaviest.label} ({heaviest.tokens} tok, "
                     f"{100*heaviest.tokens/total:.0f}% of tax)")
    rules_tok = sum(s.tokens for s in sources if s.category == "rules")
    lines.append(f"the AGENTS.md/CLAUDE.md files everyone argues about: "
                 f"{rules_tok} tok ({100*rules_tok/total:.0f}% of your tax)")
    backlog = [s for s in sources if s.category == "backlog"]
    if backlog:
        b = backlog[0]
        lines.append(f"biggest low-read suspect (backlog): {b.label} "
                     f"({b.tokens} tok) - inject a count, not the list?")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Measure a Claude Code setup's always-on context tax.")
    ap.add_argument("project", nargs="?", default=".", help="project dir (default: cwd)")
    ap.add_argument("--skip-hooks", action="store_true", help="do not run SessionStart hooks")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--timeout", type=int, default=20, help="per-hook timeout seconds")
    args = ap.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"not a directory: {project}", file=sys.stderr)
        return 2

    sources, method = audit(project, args.skip_hooks, args.timeout)
    if args.json:
        total = sum(s.tokens for s in sources)
        print(json.dumps({"method": method, "total_tokens": total,
                          "sources": [asdict(s) for s in sources]}, indent=2))
    else:
        print(render(sources, method))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
