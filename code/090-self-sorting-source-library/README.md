# Self-sorting source library

A naming convention on a folder of research sources only survives if something
else maintains it. Give it a week of dropping files in the moment you find them
and the folder looks exactly like it did before you started.

This is the fix: a Claude Code **skill** that keeps a source folder tidy for
you, plus a small **deterministic script** that does the mechanical, unsafe
part safely. You drop files in and say "sort new files". It reads each one,
proposes a prefix, shows you a before/after table, and renames on your say-so.

The point is not the folder. The point is that every tool that reads a folder,
[NotebookLM](https://notebooklm.google.com) synced over Google Drive, Gemini,
Claude Projects, or plain grep, uses the filename as the index. Prefix your
sources and the tool can filter on them (`summarise everything tagged REF`,
`what do the DATA files say`). The folder becomes a **library**; each notebook
is just a **view** into a subset of it, and the same source shows up in many
views without ever being re-uploaded.

## What's here

- **`sort_sources.py`** — stdlib-only helper. `scan` lists files with no prefix,
  `apply` renames from an approved map without ever clobbering a file, `check`
  exits non-zero if anything is unfiled (handy as a pre-sync gate). It reads the
  prefix list from the convention file, so it never hardcodes the rules.
- **`template/`** — what you copy into your own sources folder:
  - `CLAUDE.md` — the convention (the six starter prefixes and the naming rule).
    Edit this, not the script, to change the rules.
  - `.claude/skills/sort-sources/SKILL.md` — the skill Claude Code picks up when
    you ask it to sort. It re-reads `CLAUDE.md` every run.
- **`test_sort_sources.py`** — deterministic tests: scan, dry run, apply,
  collision handling, unknown-prefix rejection, idempotency.

## Use it

```bash
# one-time: copy the template into your sources folder
cp template/CLAUDE.md  /path/to/sources/
cp -r template/.claude /path/to/sources/
cp sort_sources.py     /path/to/sources/

# then, in that folder, just tell Claude Code:
#   "new files to sort"
# it reads CLAUDE.md, scans, proposes a before/after table, waits for your yes.
```

Run the mechanical parts on their own if you like:

```bash
python3 sort_sources.py scan  --dir /path/to/sources
python3 sort_sources.py check --dir /path/to/sources     # exit 1 if anything unfiled
python3 sort_sources.py apply --map /tmp/map.json --dir /path/to/sources --dry-run
```

## Design choices

- **The script never chooses the prefix.** Choosing `REF` vs `BG` vs `DRAFT`
  means understanding the file, which is the coding agent's job. The script is
  guard rails: scan, validate, apply, audit. It cannot corrupt your library.
- **The convention is data, not code.** Prefixes are parsed from `CLAUDE.md`.
  Start with four, add two after a week. You never touch the script.
- **Approval by default.** It proposes and waits. Flip that off once you trust
  it, by telling the skill to act without asking.

## What's still off

- The prefix choice is only as good as the model reading the file, so a genuinely
  ambiguous source (background reading vs your own draft of it) still wants a
  human glance. The skill is told to flag those rather than guess.
- It sorts the top level only. Sub-folders are ignored on purpose: a flat
  library is what the sync tools expect.

MIT. Steal what you want.
