---
name: sort-sources
description: >
  Tidy a research source folder so every file carries a prefix from the local
  convention. Trigger when the user says "sort new files", "new files to sort",
  "tidy the sources", or points at this folder and asks to organise or rename
  sources. Always propose a before/after table and wait for approval.
---

# Sort sources

You maintain a folder of research sources whose filenames are the index. The
naming convention lives in `CLAUDE.md` in the folder root. A helper script,
`sort_sources.py`, does the mechanical, safe part (scanning and renaming
without clobbering). You do the part that needs judgement: reading each file
and choosing the right prefix.

## Every run

1. **Re-read `CLAUDE.md`** in the folder root. The prefix list there is the
   truth. Never rely on a copy baked into this skill. If the user has changed
   the convention, your behaviour changes with it.

2. **Scan for unprefixed files.** Run:

   ```
   python3 sort_sources.py scan --dir .
   ```

   It prints JSON with `prefixes`, `prefixed`, and `unprefixed`. Only the
   `unprefixed` files need work.

3. **Read each unprefixed file** enough to know what it is. Skim the opening,
   the headings, the source. Decide:
   - which prefix from the convention fits (what the file *is* to the user, not
     just its file type), and
   - a short, plain title (no dates unless they matter, no version soup).

   When a file is genuinely ambiguous (could be `BG` or `DRAFT`), say so and ask
   rather than guessing.

4. **Propose a before/after table.** Show every rename as `old name → PREFIX
   Title.ext`, grouped so the user can scan it in one look. Do not rename yet.

5. **Wait for approval.** Only after the user says go, write the approved
   choices to a map file *outside* the library (or as a dotfile so it is not
   itself treated as a source), then apply:

   ```
   python3 sort_sources.py apply --map /tmp/sort-map.json --dir .
   ```

   The map is `{"old filename": {"prefix": "REF", "title": "Clean title"}}`.
   Use `--dry-run` first if you want to show exactly what would change. The
   script refuses unknown prefixes, never overwrites an existing file, and
   appends every rename to `.sources.log` for an audit trail.

6. **Confirm** what changed, and note anything you skipped or flagged as
   ambiguous.

## Rules

- Never rename without an approved table, unless the user has explicitly told
  you to stop asking and act on its own.
- Never invent a prefix that is not in `CLAUDE.md`. If a file fits nothing,
  say so and suggest adding a prefix to the convention.
- Leave already-prefixed files alone unless the user asks for a re-sort.
- The folder is flat: sources live at the top level, subfolders are ignored.
