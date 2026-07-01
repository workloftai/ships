#!/usr/bin/env python3
"""
sort_sources.py — the deterministic half of a self-sorting source library.

A naming convention on a folder of research sources only survives if something
maintains it. This script does the mechanical, safe part: it reads the prefix
list from a convention file (CLAUDE.md by default), finds files that do not yet
carry a prefix, and applies an approved rename map without ever clobbering a
file or acting twice on the same one.

It deliberately does NOT choose the prefix. Choosing REF vs BG vs DRAFT means
reading the file and understanding it, which is the coding agent's job. The
script is the guard rails: scan, validate, apply, audit.

Stdlib only. No dependencies.

Commands
--------
  scan   [--dir DIR] [--convention FILE]         list prefixed / unprefixed files as JSON
  apply  --map MAP.json [--dir DIR] [--dry-run]  apply an approved {old: {prefix,title}} map
  check  [--dir DIR] [--convention FILE]         exit 1 if any file lacks a prefix (a gate)

The convention file lists prefixes under a "## Prefixes" heading, one per line:
    - `REF` — reference material you cite
    - `DATA` — raw research outputs
Any line of that shape is picked up, so you edit CLAUDE.md, never this script.
"""
import argparse
import json
import os
import re
import sys

# Files we never treat as sources (the library's own machinery, not content).
IGNORE_NAMES = {
    "CLAUDE.md", "README.md", ".sources.log", ".DS_Store",
    "sort_sources.py", "test_sort_sources.py",
}
IGNORE_DIRS = {".claude", ".git", "__pycache__"}

CANON_SEP = " "  # canonical form is "PREFIX Title.ext"


def load_prefixes(convention_path):
    """Read the valid prefix set from the convention file's '## Prefixes' block."""
    if not os.path.exists(convention_path):
        raise SystemExit(f"convention file not found: {convention_path}")
    prefixes = []
    in_block = False
    line_re = re.compile(r"^\s*[-*]\s*`([A-Z][A-Z0-9]+)`")
    with open(convention_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.strip().lower().startswith("## "):
                in_block = line.strip().lower().startswith("## prefixes")
                continue
            if in_block:
                m = line_re.match(line)
                if m:
                    prefixes.append(m.group(1))
    if not prefixes:
        raise SystemExit(
            f"no prefixes found under a '## Prefixes' heading in {convention_path}"
        )
    # Longest first so DATA is tested before a hypothetical DA.
    return sorted(set(prefixes), key=len, reverse=True)


def has_prefix(name, prefixes):
    """A file is prefixed if its name starts with 'PREFIX' + space or underscore."""
    for p in prefixes:
        for sep in (" ", "_"):
            if name.startswith(p + sep):
                return p
    return None


def list_sources(directory):
    """Top-level files only. Sources live flat; the folder is the library."""
    out = []
    for entry in sorted(os.listdir(directory)):
        full = os.path.join(directory, entry)
        if entry in IGNORE_NAMES or entry.startswith("."):
            continue
        if os.path.isdir(full):
            continue
        out.append(entry)
    return out


def clean_title(title):
    """Normalise a proposed title: collapse whitespace, drop path-illegal chars."""
    title = re.sub(r"[\\/:*?\"<>|]", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    return title


def canonical_name(prefix, title, ext):
    title = clean_title(title)
    ext = ext if ext.startswith(".") or ext == "" else "." + ext
    return f"{prefix}{CANON_SEP}{title}{ext}"


def cmd_scan(args):
    prefixes = load_prefixes(args.convention)
    prefixed, unprefixed = [], []
    for name in list_sources(args.dir):
        p = has_prefix(name, prefixes)
        rec = {"name": name, "ext": os.path.splitext(name)[1]}
        if p:
            rec["prefix"] = p
            prefixed.append(rec)
        else:
            unprefixed.append(rec)
    json.dump(
        {"prefixes": prefixes, "prefixed": prefixed, "unprefixed": unprefixed},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def cmd_check(args):
    prefixes = load_prefixes(args.convention)
    missing = [n for n in list_sources(args.dir) if not has_prefix(n, prefixes)]
    if missing:
        print(f"{len(missing)} file(s) without a prefix:")
        for n in missing:
            print(f"  {n}")
        return 1
    print("all sources carry a prefix")
    return 0


def _resolve_target(directory, desired, existing):
    """Avoid clobbering: if 'PREFIX Title.ext' is taken, append ' (2)', ' (3)'..."""
    base, ext = os.path.splitext(desired)
    candidate, n = desired, 1
    while candidate in existing or os.path.exists(os.path.join(directory, candidate)):
        n += 1
        candidate = f"{base} ({n}){ext}"
    return candidate


def cmd_apply(args):
    prefixes = set(load_prefixes(args.convention))
    with open(args.map, encoding="utf-8") as fh:
        mapping = json.load(fh)

    planned, skipped, errors = [], [], []
    reserved = set(os.listdir(args.dir))

    for old, spec in mapping.items():
        src = os.path.join(args.dir, old)
        if not os.path.exists(src):
            errors.append((old, "source not found"))
            continue
        if isinstance(spec, str):
            # A full target filename was given; trust it but validate the prefix.
            target = spec
            pfx = target.split(" ")[0].split("_")[0]
        else:
            pfx = spec.get("prefix", "")
            title = spec.get("title", os.path.splitext(old)[0])
            target = canonical_name(pfx, title, os.path.splitext(old)[1])
        if pfx not in prefixes:
            errors.append((old, f"unknown prefix '{pfx}'"))
            continue
        if target == old:
            skipped.append((old, "already canonical"))
            continue
        reserved.discard(old)
        final = _resolve_target(args.dir, target, reserved)
        reserved.add(final)
        planned.append((old, final))

    for old, new in planned:
        arrow = "→"
        print(f"  {old}  {arrow}  {new}")
    for old, why in skipped:
        print(f"  (skip) {old}: {why}")
    for old, why in errors:
        print(f"  (error) {old}: {why}", file=sys.stderr)

    if args.dry_run:
        print(f"\ndry run: {len(planned)} rename(s), {len(errors)} error(s)")
        return 1 if errors else 0

    log_path = os.path.join(args.dir, ".sources.log")
    with open(log_path, "a", encoding="utf-8") as log:
        for old, new in planned:
            os.rename(os.path.join(args.dir, old), os.path.join(args.dir, new))
            log.write(f"{old}\t{new}\n")

    print(f"\napplied {len(planned)} rename(s), {len(errors)} error(s)")
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan")
    s.add_argument("--dir", default=".")
    s.add_argument("--convention", default="CLAUDE.md")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("check")
    c.add_argument("--dir", default=".")
    c.add_argument("--convention", default="CLAUDE.md")
    c.set_defaults(func=cmd_check)

    a = sub.add_parser("apply")
    a.add_argument("--map", required=True)
    a.add_argument("--dir", default=".")
    a.add_argument("--convention", default="CLAUDE.md")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    # Convention defaults sit inside --dir unless an absolute path was given.
    if not os.path.isabs(args.convention):
        args.convention = os.path.join(args.dir, args.convention)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
