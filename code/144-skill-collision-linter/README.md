# skill-collision-linter

Find the skills and slash-commands in your Claude Code setup whose triggers
overlap, so you can tell which ones will fight over the same phrase before one
silently shadows the other.

A setup accretes skills over months. Each one looks fine in its own file. The
failure mode lives *between* the files: two skills whose triggers overlap, so a
phrase you type could reasonably fire either, and which one wins is luck. Nobody
lints for this, because the collision does not exist in any single file.

This is one stdlib-only, read-only Python file. It never writes to your setup.

## Run it

```bash
python3 skill_lint.py                 # scans ~/.claude/skills + ~/.claude/commands
python3 skill_lint.py --all           # also include plugin/marketplace skills
python3 skill_lint.py PATH ...        # scan specific dirs or files
python3 skill_lint.py --json          # machine-readable
python3 skill_lint.py --min-score 30  # only the louder collisions
```

## What it looks at

For every skill/command it reads the frontmatter `name`, the `description`, and
the body, then extracts what each one claims to trigger on. It ranks pairs by
risk using these signals, strongest first:

- **name-prefix** — one command name is a prefix of another (`/linkedin` vs
  `/linkedinpost`), so a bare invocation is genuinely ambiguous.
- **shared trigger phrase** — two skills quote the same natural-language trigger
  (`"anything for us?"`).
- **shared slash-token** — two skills both reference the same `/token`. Path
  fragments like `/home/you` are excluded; only real command tokens count.
- **lexical overlap** — how much their descriptions lean on the same content
  words, a proxy for topic overlap (`pizza` vs `sourdough`).

Declared relationships are respected: if one skill says it is an *alias for* or
*distinct from* another **and names it**, the pair is downgraded rather than
hidden, so intentional pairings do not drown the accidental ones.

## What it does not do

It measures overlap, not intent. It flags candidates and explains why; whether
an overlap is a bug or a deliberate alias is your call. Lexical overlap is a
heuristic, not semantics. It reads what a skill *says* it triggers on, not what
the model actually does at dispatch time. Treat the ranking as a shortlist to
review, not a verdict.

MIT-licensed. Part of the Workloft Ships series.
