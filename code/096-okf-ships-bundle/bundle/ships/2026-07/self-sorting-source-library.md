---
type: Ship
title: "A source library that files itself"
description: "A naming convention on a folder of research sources only survives if something maintains it. We gave that job to a Claude Code skill: drop files in, say 'sort new files', and it reads each one, proposes a prefix, and renames on your approval. The folder becomes a library every tool can filter."
resource: https://workloft.ai/ships/self-sorting-source-library-2026-07-01.html
tags: [workloft, ship]
timestamp: 2026-07-01T00:00:00Z
---
_1 July 2026 · tool · by Alfred + Bob_

# A source library that files itself

**A naming convention on a folder only survives if something else maintains it. Drop files in the moment you find them, promise yourself you will tidy later, and a week on the folder looks like it always did. So we gave the tidying to a Claude Code skill: drop research files into one folder, say "sort new files", and it reads each one, proposes a prefix, and renames on your approval. The folder becomes a library every tool can filter, from NotebookLM to plain grep.**

## What we did

The idea has been going round for NotebookLM users: prefix your source filenames so you can recognise them at a glance and filter on them. It works because the tools that read a folder, NotebookLM synced over Google Drive, Gemini, Claude Projects, a plain `grep`, all treat the filename as the index. Give a file a prefix like `REF` or `DATA` and you can toggle a subset in or out, or ask "summarise everything tagged REF" and have it actually work.

The thing that kills it is the renaming. Nobody keeps it up by hand. So we built two halves and handed the boring one to the machine:

- A **convention** lives in a `CLAUDE.md` in the folder: the prefix list (REF, DATA, BG, STUDY, DRAFT, JUNK) and the naming rule. Edit this to change the rules, never the code.
- A **skill** (`.claude/skills/sort-sources/SKILL.md`) that Claude Code picks up when you say "sort new files". It re-reads the convention each run, reads each unfiled file to decide what it actually is, shows a before-and-after table, and waits for your yes.
- A **deterministic script** (`sort_sources.py`) that does the mechanical part safely: `scan` lists files with no prefix, `apply` renames from an approved map without ever overwriting a file, `check` exits non-zero if anything is unfiled.

The split is the whole point. Choosing REF versus BG versus DRAFT means reading the file and understanding it, which is the model's job. Renaming a hundred files without clobbering one, and logging what changed, is the script's job. The model cannot corrupt your library, and the script never has to guess.

## Why it was worth doing

It turns a folder into a **library**, and every notebook or project into a **view**: a chosen subset of that library. The same source shows up in three notebooks without being copied, because the folder is the single source of truth and nothing is re-uploaded to organise it. On a full NotebookLM notebook, near its source cap, that is the difference between scanning for a file and reading its prefix.

The broader lesson has nothing to do with NotebookLM. A convention is only as good as its upkeep, and upkeep is exactly the kind of dull, repetitive judgement a coding agent is good at and humans quietly abandon. The trick is to keep the rules as data the agent reads, not logic baked into the agent, so you can change your mind next week without touching code.

## What's now in the stack

- A drop-in `template/`: the `CLAUDE.md` convention and the `sort-sources` skill you copy into any sources folder.
- `sort_sources.py`: stdlib-only, `scan` / `apply` / `check`, no-clobber renames, an append-only audit log.
- A deterministic test suite covering scan, dry run, apply, collision handling, unknown-prefix rejection and idempotency.
- All of it is public on [GitHub](https://github.com/workloftai/ships/tree/main/code/090-self-sorting-source-library). Steal what you like.

## What's still off

The prefix choice is only as good as the model reading the file, so a genuinely ambiguous source (background reading versus your own draft of it) still wants a human glance. The skill is told to flag those rather than guess. And it sorts the top level only: sub-folders are ignored on purpose, because a flat library is what the sync tools expect. Approval is on by default. You can turn it off once you trust it, which is a decision, not an accident.

## FAQ

### How do you keep a folder of research sources organised automatically?

Write the naming convention into a `CLAUDE.md` in the folder, then add a Claude Code skill that re-reads that file each run, scans for files without a prefix, reads each one to choose the right prefix, and renames on your approval. A small deterministic script does the scanning and renaming safely so it never overwrites a file. You drop files in and say "sort new files".

### Why prefix source filenames for NotebookLM, Gemini or Claude Projects?

Those tools show the filename as the index and let you filter on it, so a prefix like REF or DATA lets you toggle a subset in or out and ask things like "summarise everything tagged REF". The folder becomes a single library and each notebook is just a view into a subset of it, with the same source reused across notebooks without re-uploading.

### Should an AI agent rename files without asking?

By default no. The skill proposes a before-and-after table and waits for approval, and the underlying script refuses unknown prefixes, never overwrites an existing file, and logs every rename for an audit trail. You can turn approval off once you trust it, but the safe default is propose-then-confirm.
