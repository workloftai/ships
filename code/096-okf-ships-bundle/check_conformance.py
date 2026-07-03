#!/usr/bin/env python3
"""Check a directory tree against OKF v0.1 conformance (SPEC §9).

1. Every non-reserved .md file has a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty `type` field.
3. Reserved files (index.md, log.md) follow their sections when present
   (checked loosely: index.md contains at least one markdown list link).

Exit 0 = conformant, 1 = violations (listed).
"""

import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
violations = []
concepts = 0

for p in sorted(root.rglob("*.md")):
    rel = p.relative_to(root)
    text = p.read_text()
    if p.name in ("index.md", "log.md"):
        if p.name == "index.md" and not re.search(r"^\* \[.+\]\(.+\)", text, re.M):
            violations.append(f"{rel}: index.md has no list entries")
        continue
    m = FM_RE.match(text)
    if not m:
        violations.append(f"{rel}: no parseable frontmatter block")
        continue
    if not re.search(r"^type:\s*\S", m.group(1), re.M):
        violations.append(f"{rel}: missing or empty required `type` field")
    concepts += 1

if violations:
    print(f"NOT CONFORMANT — {len(violations)} violation(s):")
    for v in violations:
        print(" ", v)
    sys.exit(1)
print(f"conformant: {concepts} concept documents, 0 violations")
