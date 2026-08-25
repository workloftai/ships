#!/usr/bin/env python3
"""skill-collision-linter — find skills that fight over the same trigger.

A Claude Code setup accretes skills and slash-commands over months. Each one
looks fine alone. The failure mode is between them: two skills whose triggers
overlap, so a phrase the user types could reasonably fire either, and which one
wins is luck. Nobody lints for this, because each skill is a separate file and
the collision only exists in the space between the files.

This tool reads your skill and command definitions, extracts what each one
claims to trigger on (its name, the slash-tokens it mentions, the phrases it
quotes, the words it leans on), and reports the pairs most likely to collide,
ranked by risk. It is stdlib-only and read-only: it never writes to your setup.
It flags candidates; the judgement of whether an overlap is a bug or a
deliberate alias is left to you, and declared aliases are downgraded so they do
not drown the real problems.

Collision signals, strongest first:
  - name-prefix: one command name is a prefix of another (`/linkedin` vs
    `/linkedinpost`), so a bare invocation is genuinely ambiguous.
  - shared trigger phrase: two skills quote the same natural-language trigger
    ("anything for us?").
  - shared slash-token: two skills both reference the same /token.
  - lexical overlap: how much their descriptions lean on the same content
    words (a proxy for topic overlap, e.g. pizza vs sourdough).

Usage:
    python3 skill_lint.py [PATH ...] [--all] [--json] [--min-score N]

With no PATH, scans ~/.claude/skills/*/SKILL.md and ~/.claude/commands/*.md
(your own layer). --all also includes plugin/marketplace skills, which are not
yours to edit but can still shadow your triggers.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Words too common to signal topic overlap. Kept deliberately small; the goal is
# to strip glue, not to build a stemmer.
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "into", "your", "you", "from",
    "his", "her", "him", "not", "but", "when", "what", "which", "whenever",
    "usage", "alfred", "bob", "workloft", "skill", "use", "used", "uses",
    "using", "then", "them", "they", "are", "was", "will", "can", "get", "gets",
    "one", "two", "three", "want", "wants", "here", "there", "each", "per",
    "via", "onto", "off", "out", "own", "any", "all", "new", "just", "only",
    "first", "second", "back", "over", "after", "before", "about", "plus",
    "never", "always", "returns", "return", "run", "runs", "shape", "type",
    "line", "give", "gives", "him", "she", "how", "why", "who", "let", "lets",
}

# A relationship keyword only counts as "declared" when it sits next to the
# OTHER skill's name (see declares_relationship), so these stay broad.
REL_RE = re.compile(r"\balias(?:es)? (?:for|of|to)?\b|\bshorthand (?:for|of)\b"
                    r"|\bdistinct from\b|\bnot to be confused with\b|\bsame as\b", re.I)
# A slash-command trigger, NOT a filesystem path: reject if the char before the
# slash is a word char or another slash (i.e. mid-path like /home/workloft), and
# reject if the token is immediately followed by / or . (a path segment or file).
SLASH_RE = re.compile(r"(?<![\w/])/([a-z][a-z0-9:_-]{1,30})(?![\w/.])")
QUOTED_RE = re.compile(r'["“‘]([^"”’]{3,60})["”’]')
WORD_RE = re.compile(r"[a-z][a-z0-9+-]{2,}")


@dataclass
class Skill:
    name: str
    path: Path
    description: str
    body: str
    slash: set = field(default_factory=set)
    phrases: set = field(default_factory=set)
    words: set = field(default_factory=set)

    @property
    def text(self) -> str:
        return f"{self.description}\n{self.body}"


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Tolerant of missing/loose YAML."""
    fm: dict = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            block = raw[3:end]
            body = raw[end + 4:]
            key = None
            for line in block.splitlines():
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
                if m:
                    key = m.group(1).strip().lower()
                    val = m.group(2).strip().strip('"“”')
                    fm[key] = val
                elif key and line.strip():
                    fm[key] = (fm.get(key, "") + " " + line.strip()).strip()
    return fm, body


def content_words(text: str) -> set:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS and len(w) >= 4}


def load_skill(path: Path) -> Skill | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm, body = parse_frontmatter(raw)
    # name: frontmatter, else the command filename, else the skill dir name.
    name = fm.get("name") or (path.parent.name if path.name == "SKILL.md" else path.stem)
    name = name.strip().lower()
    desc = fm.get("description", "")
    s = Skill(name=name, path=path, description=desc, body=body)
    s.slash = {t.lower() for t in SLASH_RE.findall(s.text)}
    s.slash.discard(name)  # a skill naming its own /token is not a collision
    s.phrases = {p.strip().lower() for p in QUOTED_RE.findall(s.description)}
    s.words = content_words(s.description)
    return s


def discover(paths: list[Path], include_all: bool) -> list[Skill]:
    home = Path.home()
    if not paths:
        paths = [home / ".claude" / "skills", home / ".claude" / "commands"]
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(p.glob("*/SKILL.md"))
            files.extend(p.glob("*.md"))
    if include_all:
        pl = home / ".claude" / "plugins"
        if pl.is_dir():
            files.extend(pl.rglob("SKILL.md"))
    seen, skills = set(), []
    for f in sorted(set(files)):
        if f.name.upper() == "README.md":
            continue
        s = load_skill(f)
        if s and s.name and (s.name, str(f)) not in seen:
            seen.add((s.name, str(f)))
            skills.append(s)
    return skills


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def declares_relationship(text: str, other: str) -> bool:
    """True if `text` states a deliberate relationship (alias / distinct-from) to
    the skill named `other`: a relationship keyword within ~40 chars of the name.
    This is what separates an intentional pairing from an accidental collision."""
    low = text.lower()
    for m in re.finditer(re.escape(other.lower()), low):
        window = low[max(0, m.start() - 45): m.end() + 45]
        if REL_RE.search(window):
            return True
    return False


@dataclass
class Collision:
    a: str
    b: str
    score: int
    severity: str
    reasons: list
    declared: bool
    fix: str


def name_prefix(a: str, b: str) -> bool:
    lo, hi = sorted((a, b), key=len)
    return len(lo) >= 3 and hi.startswith(lo) and lo != hi


def analyse(skills: list[Skill]) -> list[Collision]:
    out = []
    for a, b in itertools.combinations(skills, 2):
        reasons, score = [], 0.0

        if name_prefix(a.name, b.name):
            score += 55
            reasons.append(f"name '{min(a.name, b.name, key=len)}' is a prefix of "
                           f"'{max(a.name, b.name, key=len)}', so a bare slash is ambiguous")

        shared_ph = a.phrases & b.phrases
        if shared_ph:
            score += 45
            reasons.append("share trigger phrase(s): " + ", ".join(sorted(shared_ph)[:3]))

        shared_slash = a.slash & b.slash
        if shared_slash:
            score += 35
            reasons.append("both reference /" + ", /".join(sorted(shared_slash)[:3]))

        jac = jaccard(a.words, b.words)
        if jac > 0:
            score += round(jac * 60)
            if jac >= 0.12:
                common = sorted(a.words & b.words)
                reasons.append(f"lexical overlap {jac:.0%} on: "
                               f"{', '.join(common[:6])}{'…' if len(common) > 6 else ''}")

        if not reasons:
            continue

        # Declared relationship: an alias/shorthand or an explicit "distinct
        # from" that names the OTHER skill means the author already knows and
        # chose it. Downgrade, don't hide. The name must sit next to the keyword,
        # so "NOT the Workloft page" no longer masks a real collision.
        declared = declares_relationship(a.text, b.name) or declares_relationship(b.text, a.name)
        if declared:
            score *= 0.35

        score = int(min(round(score), 100))
        if score < 8:
            continue

        sev = "HIGH" if score >= 55 else "MED" if score >= 30 else "LOW"
        if declared:
            sev = "LOW"
            reasons.append("declared alias / explicitly distinguished (intentional)")

        if name_prefix(a.name, b.name):
            fix = "make one name not a prefix of the other, or add a clear disambiguator"
        elif shared_ph or shared_slash:
            fix = "give each a distinct trigger, or make one an explicit alias of the other"
        else:
            fix = "sharpen the descriptions so the boundary between them is explicit"

        out.append(Collision(a.name, b.name, score, sev, reasons, bool(declared), fix))
    out.sort(key=lambda c: (-c.score, c.a, c.b))
    return out


def render(skills: list[Skill], cols: list[Collision], min_score: int) -> str:
    shown = [c for c in cols if c.score >= min_score]
    lines = ["skill-collision-linter",
             f"scanned {len(skills)} skills/commands, "
             f"{len(shown)} collision pair(s) at score >= {min_score}", ""]
    if not shown:
        lines.append("no collisions above threshold. either you are tidy or your triggers are vague.")
        return "\n".join(lines)
    lines.append(f"{'severity':<9}{'score':<7}pair")
    lines.append("-" * 64)
    for c in shown:
        lines.append(f"{c.severity:<9}{c.score:<7}/{c.a}  x  /{c.b}")
        for r in c.reasons:
            lines.append(f"           - {r}")
        lines.append(f"           fix: {c.fix}")
        lines.append("")
    highs = sum(c.severity == "HIGH" for c in shown)
    lines.append(f"{highs} HIGH-severity collision(s) worth fixing first.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Find colliding skill/command triggers.")
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="also scan plugin/marketplace skills")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-score", type=int, default=8)
    args = ap.parse_args(argv)

    skills = discover(args.paths, args.all)
    if not skills:
        print("no skills or commands found. pass a path, or check ~/.claude.", file=sys.stderr)
        return 2
    cols = analyse(skills)

    if args.json:
        print(json.dumps({
            "scanned": len(skills),
            "skills": sorted(s.name for s in skills),
            "collisions": [c.__dict__ for c in cols if c.score >= args.min_score],
        }, indent=2))
    else:
        print(render(skills, cols, args.min_score))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
