#!/usr/bin/env python3
"""Build an OKF v0.1 knowledge bundle from the Workloft Ships library.

Reads the machine-readable markdown siblings in workloft-site/ships/ and
emits a conformant Open Knowledge Format bundle (SPEC.md, Google Cloud
knowledge-catalog, v0.1 draft): one concept per ship with required `type`
frontmatter, recommended fields filled from what the siblings already
carry, a generated ships/index.md and a root index.md declaring
okf_version. Grouped by year-month for a hierarchy that means something.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

SRC = Path("/home/workloft/workloft-site/ships")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/workloft/okf-ships/bundle")

META_RE = re.compile(r"^_(\d{2} \w+ \d{4}) · (\w+) · by (.+?)_$", re.M)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.md$")
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def fm_field(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip() if m else ""


def yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def convert(path: Path) -> dict | None:
    text = path.read_text()
    fm_match = FM_RE.match(text)
    if not fm_match:
        return None
    fm, body = fm_match.group(1), text[fm_match.end():]
    date_m = DATE_RE.search(path.name)
    if not date_m:
        return None
    date = date_m.group(1)
    title = fm_field(fm, "title").removesuffix(" — Workloft Ships")
    desc = fm_field(fm, "description")
    canonical = fm_field(fm, "canonical")
    meta_m = META_RE.search(body)
    category = meta_m.group(2) if meta_m else "ship"

    slug = path.name.removesuffix(".md").removesuffix("-" + date)
    month = date[:7]
    concept_rel = Path("ships") / month / f"{slug}.md"

    out = OUT / concept_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = "\n".join([
        "---",
        "type: Ship",
        f"title: {yaml_str(title)}",
        f"description: {yaml_str(desc)}",
        f"resource: {canonical}",
        f"tags: [workloft, {category}]",
        f"timestamp: {date}T00:00:00Z",
        "---",
    ])
    out.write_text(frontmatter + "\n" + body.lstrip("\n"))
    return {"rel": concept_rel, "title": title, "desc": desc,
            "date": date, "month": month, "category": category}


def one_line(desc: str, limit: int = 140) -> str:
    d = desc.split(". ")[0].rstrip(".") + "."
    return d if len(d) <= limit else d[: limit - 1].rstrip() + "…"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    concepts = []
    for p in sorted(SRC.glob("*.md")):
        if p.name == "index.md":
            continue
        c = convert(p)
        if c:
            concepts.append(c)
    concepts.sort(key=lambda c: c["date"], reverse=True)

    # Per-month index.md files
    months: dict[str, list[dict]] = {}
    for c in concepts:
        months.setdefault(c["month"], []).append(c)
    for month, items in months.items():
        lines = [f"# Ships — {month}", ""]
        lines += [f"* [{c['title']}]({c['rel'].name}) - {one_line(c['desc'])}"
                  for c in items]
        (OUT / "ships" / month / "index.md").write_text("\n".join(lines) + "\n")

    # ships/index.md — one section per month, newest first
    lines = ["# Workloft Ships by month", ""]
    for month in sorted(months, reverse=True):
        lines.append(f"* [{month}]({month}/) - {len(months[month])} ships")
    (OUT / "ships" / "index.md").write_text("\n".join(lines) + "\n")

    # Root index.md with okf_version declaration (the one indexed file
    # where frontmatter is permitted, per SPEC §11)
    root = [
        "---",
        'okf_version: "0.1"',
        "---",
        "# Workloft Ships knowledge bundle",
        "",
        f"{len(concepts)} shipped builds from workloft.ai/ships, one concept "
        "per ship, in Open Knowledge Format. Each concept records what was "
        "built, why it was worth doing and what is still off.",
        "",
        "# Sections",
        "",
        f"* [ships/](ships/) - all {len(concepts)} ships, grouped by month",
    ]
    (OUT / "index.md").write_text("\n".join(root) + "\n")

    n_files = sum(1 for _ in OUT.rglob("*.md"))
    size_kb = sum(f.stat().st_size for f in OUT.rglob("*.md")) // 1024
    print(f"bundle: {len(concepts)} concepts, {n_files} files, {size_kb} KB -> {OUT}")


if __name__ == "__main__":
    main()
