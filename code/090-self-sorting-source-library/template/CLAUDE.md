# Sources library

This folder is a library of research sources. Any tool that reads a folder or
syncs it (NotebookLM via Google Drive, Gemini, Claude Projects, a plain grep)
sees these filenames, so the name is the index. Every source carries a prefix
so I can recognise it at a glance and filter on it inside those tools.

A notebook or a project is just a **view**: a chosen subset of this library.
The same source can appear in three notebooks without being copied. The folder
is the single source of truth; nothing is ever re-uploaded to organise it.

## Prefixes

- `REF` — reference material I cite or come back to (specs, docs, canonical papers)
- `DATA` — raw research outputs (exports, datasets, transcripts, scrape results)
- `BG` — background reading (articles, explainers, context I skim)
- `STUDY` — things I am actively learning from
- `DRAFT` — anything I wrote myself (notes, half-formed thinking, outlines)
- `JUNK` — explicitly decided this is not useful, but I want to keep it

Do not treat this list as fixed. Start small, add a prefix when a real pile of
files wants one. Two extra prefixes after a week of use beats six guessed on
day one.

## Naming rule

Canonical form is `PREFIX Title.ext`, for example `REF NotebookLM source caps.pdf`.
The prefix is a whole word from the list above, then a single space, then a
short human-readable title, then the original extension. Keep the title plain:
no dates unless they matter, no version soup.

## The filing rule

When I say "sort new files", "new files to sort", or point at this folder and
ask you to tidy it, follow the `sort-sources` skill. In short: read each file
that has no prefix yet, choose the best prefix from the list above based on
what the file actually is, propose a before/after table, and wait for my
approval before renaming anything. Re-read this file each run so the convention
here always wins, never a copy baked into the skill.
