# We gave our agent a memory that reorganises itself

**Date:** 27 June 2026
**Author:** Alfred + Bob
**Category:** agent

We opened up our agent's long-term memory expecting a quick tidy-up and found a third of it was invisible. There were 218 memory files on disk. The index that loads at the start of every session listed about 135 of them, and the index itself had grown past its own line cap, so the harness was loading only the first slice and dropping the rest in silence. The agent had no way to know. We rebuilt the whole thing as a two-level graph that keeps itself honest.

## What we did

The memory is one markdown file per fact, plus a root index that gets read into context on every session. The root was one long flat list, one line per memory, and it had reached 214 lines against a 200-line budget. Anything past the cut-off never loaded. On top of that, dozens of files had been written over the months but never added to the index at all.

We replaced the flat list with a thin root that points only at topic index files, the map-of-content pattern. Each topic file lists the memories for its area, the root lists the topics. The agent loads the thin root, opens the one topic it needs, then reads the memory. We sorted all 216 real memories into 14 topic files and the root dropped from 214 lines to 30. Then we added the machinery to stop it rotting again: a nightly check, a metadata backfill so every memory carries a created and a last-verified date, and a small eval.

## Why it was worth doing

The failure mode is the dangerous kind, the silent kind. A flat index does not error when it overflows. It just stops loading, and recall quietly degrades as the store grows. The two-level version bounds what loads at session start no matter how big the memory gets, because the root only ever holds a list of topics. Content-based recall, finding a memory by what it says, still runs through our vector layer. The topic files are for navigation. The two jobs are different and we stopped trying to make one list do both.

The nightly check earns its keep on day one. It looks for memories no topic links to, links that point at nothing, the same memory filed twice, a topic that has grown past its cap, and a root that has crept over its line budget. The first run flagged two topic files that had grown too big. We split them, reran, and it went green.

## What's still off

The nightly check reports, it does not repair. We kept it read-only on purpose: a wrong prompt is wrong once, but a wrong memory is wrong forever, so deletion and merging stay a human decision. Stale entries get surfaced for review, never auto-removed. The created dates fell back to file timestamps because this particular memory store is not under git. And the eval tests reachability, that each known question still resolves to its file along the path the agent actually walks, not yet the quality of the answer.

## Steal this: the nightly check

Read-only. Exits non-zero on any problem so a cron can alert. No external dependencies.

```python
#!/usr/bin/env python3
"""maintain.py - the self-maintaining check for a map-of-content memory."""
import argparse, datetime as dt, re, sys
from pathlib import Path

LINK_RE = re.compile(r"\]\(([^)]+\.md)\)")
FM_RE = re.compile(r"^---\s*$")
STRUCTURE = {"MEMORY.md"}
NON_MEMORY = {"MEMORY_PRUNE_PROPOSALS.md", "SOP_ROUTING.md"}

def is_moc(name): return name.startswith("MOC-")

def frontmatter(path):
    out = {}
    try: lines = path.read_text(encoding="utf-8").splitlines()
    except Exception: return out
    if not lines or not FM_RE.match(lines[0]): return out
    for line in lines[1:]:
        if FM_RE.match(line): break
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":"); out[k.strip()] = v.strip().strip('"')
    return out

def linked_targets(path):
    try: return [Path(m).name for m in LINK_RE.findall(path.read_text(encoding="utf-8"))]
    except Exception: return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("memory_dir", nargs="?", default=".")
    ap.add_argument("--cap", type=int, default=25)
    ap.add_argument("--root-max", type=int, default=40)
    ap.add_argument("--stale-days", type=int, default=60)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    root_dir = Path(args.memory_dir).expanduser().resolve()
    today = dt.date.today()
    all_md = {p.name for p in root_dir.glob("*.md")}
    mocs = sorted(n for n in all_md if is_moc(n))
    memories = sorted(n for n in all_md
                      if not is_moc(n) and n not in STRUCTURE and n not in NON_MEMORY)

    linked_by = {m: [] for m in memories}; broken = []; moc_counts = {}
    for moc in mocs:
        targets = linked_targets(root_dir / moc); moc_counts[moc] = len(targets)
        for t in targets:
            if t in linked_by: linked_by[t].append(moc)
            elif t not in all_md: broken.append((moc, t))

    root_links = set()
    for t in linked_targets(root_dir / "MEMORY.md"):
        root_links.add(t)
        if t not in all_md: broken.append(("MEMORY.md", t))

    orphans = [m for m, w in linked_by.items() if not w and m not in root_links]
    dupes = {m: w for m, w in linked_by.items() if len(w) > 1}
    over_cap = {m: c for m, c in moc_counts.items() if c > args.cap}
    root_lines = len((root_dir / "MEMORY.md").read_text(encoding="utf-8").splitlines()) \
        if (root_dir / "MEMORY.md").exists() else 0

    stale = []
    for m in memories:
        lv = frontmatter(root_dir / m).get("last_verified", "")
        try: age = (today - dt.date.fromisoformat(lv)).days
        except ValueError: continue
        if age > args.stale_days: stale.append((m, age))

    problems = bool(orphans or broken or dupes or over_cap or root_lines > args.root_max)
    if not (args.quiet and not problems):
        print(f"memory-moc: {len(memories)} memories / {len(mocs)} MOCs, root {root_lines}/{args.root_max}")
        for moc, c in sorted(over_cap.items()): print(f"  OVER CAP: {moc} has {c} (cap {args.cap}) - split it")
        for m in orphans: print(f"  ORPHAN: {m} is in no MOC")
        for src, tgt in broken: print(f"  BROKEN: {src} -> missing {tgt}")
        for m, w in dupes.items(): print(f"  DUPE: {m} in {', '.join(w)}")
        if stale: print(f"  STALE: {len(stale)} unverified >{args.stale_days}d - review, don't auto-delete")
        if not problems: print("  all clear")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
```

The rule underneath it all: keep the always-loaded index thin, and let navigation and recall be two separate jobs.
