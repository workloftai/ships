# context-tax — measure where your Claude Code token budget actually goes

The internet is arguing about whether `AGENTS.md` / `CLAUDE.md` files earn their
token cost. One study says those files are 60% of everything an agent reads;
another benchmark says they add 23% cost for zero measurable gain. Both are
arguing about the wrong file.

The always-on tax in a real setup is not one file. It is a stack of injections
that ride into **every session before you type a word**: the CLAUDE.md chain, the
memory index, and — the part nobody measures — whatever your SessionStart hooks
print. Files on disk are easy to eyeball. Hook output is invisible until you run
it, and that is usually where the weight is hiding.

`context-tax` reads them all, runs the hooks, and prints a table ranked by weight.
Stdlib-only, read-only (it never writes to your project). The one thing it
executes is your SessionStart hook commands, because their output *is* the hidden
tax and there is no other way to weigh it. Pass `--skip-hooks` to turn that off.

## Run it

```bash
python3 context_tax.py [PROJECT_DIR] [--skip-hooks] [--json]
```

`PROJECT_DIR` defaults to the current directory. Token counts use `tiktoken` if it
is importable, otherwise a `chars/4` estimate — close enough to rank, and ranking
is the point.

## What it found on our own setup

```
source                                  category    tokens   share
------------------------------------------------------------------
MEMORY.md (memory index)                memory        1654   21.7%
hook: loop_board_session_start.sh       backlog       1608   21.1%
~/CLAUDE.md                             rules         1359   17.9%
hook: fleet-registry-hook.sh            routing       1239   16.3%
hook: recent_telegram_session_start.py  other         1039   13.7%
hook: sop_index_session_start.py        other          631    8.3%
~/conexus/AGENTS.md                     rules           74    1.0%
~/conexus/CLAUDE.md                     rules            5    0.1%
------------------------------------------------------------------
TOTAL always-on tax                                   7609
```

**7,609 tokens before the first word.** The `AGENTS.md` / `CLAUDE.md` files
everyone is arguing about are 19% of the tax, and our repo's actual `AGENTS.md` is
**74 tokens — one percent**. The argument is aimed at the smallest thing in the
stack.

Where the tax really lives: the memory index (22%), a **backlog board** injected
in full every session (21%, 39 research items most of which are never touched that
session), and a stack of hook-emitted routing tables. The single cleanest cut is
the backlog: inject a *count* plus today's due items, not all 39 lines, and you
reclaim about 1,400 tokens per session at near-zero information loss.

## It caught its own bug

On the first run the tool reported the loop board as **0 tokens** — it zeroed out
the exact source the whole audit is about. The hook output carries emoji and
box-drawing bytes, and a strict UTF-8 decode threw, so the source silently fell to
zero. A tool that drops the biggest low-read suspect is worse than no tool, so the
subprocess decode is now `errors="replace"`. The number went from a false 0 to a
real 1,608. Catching your own false negative is the cheapest honesty there is.

## What it does not do

- It measures **weight**, not **read-probability**. It buckets sources by role
  (rules / memory / routing / backlog) so you can judge which pinned tokens are
  load-bearing every turn and which are reference material that could load on
  demand — but it cannot tell you how often a given block is actually consulted.
- Token counts are an estimate unless `tiktoken` is present.
- It runs your SessionStart hooks. They are assumed read-only (they usually just
  echo files or query a local DB). If yours are not, use `--skip-hooks`.
- Tool-schema and MCP-instruction injections are not counted; this measures the
  file + hook layer you control.

## The lesson

Before you delete a line of `AGENTS.md` because a benchmark said it does not pay,
measure your actual tax. The file everyone benchmarks is probably not where your
tokens go. Your always-on injections are.
