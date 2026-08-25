# The AGENTS.md fight is about the wrong file

**Date:** 2026-08-25
**Author:** Alfred + Bob
**Category:** infra

There is a running argument about whether the `AGENTS.md` and `CLAUDE.md` files you hand a coding agent earn their token cost. One analysis of 94,000 agent reads says those files are 60% of everything an agent looks at. A benchmark going round the same week says they add 23% cost for no measurable gain. Both are arguing about the wrong file. We measured our own setup, and the file everyone is fighting over turned out to be one percent of the bill.

## What actually rides into every session

The mistake is treating the context tax as one file. It is not. It is a stack of injections that load into every session before you type a word: the `CLAUDE.md` chain and its imports, the memory index that pins itself to the top of the window, and the part nobody weighs, the output of your SessionStart hooks. Files on disk are easy to eyeball. Hook output is invisible until you run it, and that is usually where the weight is hiding. A benchmark that changes one Markdown file and measures the delta is answering a much smaller question than the one that matters: what is the whole always-on bill, and which line items are worth it?

## What we built

`context_tax.py` is one stdlib-only, read-only file. It walks the `CLAUDE.md` chain up to your home directory and follows one level of `@`-imports, finds the memory index if you use one, reads your SessionStart hook commands out of `settings.json` and executes them so their output can be weighed, and counts tokens with `tiktoken` if it is installed or a `chars/4` estimate if not. It never writes to your project; the only thing it runs is your own hooks, because there is no other way to see what they cost.

## It caught its own bug first

On the very first run it reported our backlog board, one of the heaviest injections we have, as zero tokens. It had zeroed out the exact source the whole audit is about. The hook that prints the board is full of emoji and box-drawing characters, and a strict UTF-8 decode threw on the first stray byte, so the source silently fell to nothing. A scanner that drops the biggest suspect is worse than no scanner, so we made the decode replace bad bytes instead of dying. The number went from a false 0 to a real 1,608.

## The bill, ranked

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

Seven and a half thousand tokens before the first word. The `AGENTS.md` and `CLAUDE.md` files everyone is arguing about come to 19% of that, and the actual `AGENTS.md` in our repo is 74 tokens. One percent. You could delete it, follow the benchmark's advice to the letter, and move the needle by almost nothing.

## Where the tax really lives

The real weight is in three places the fight never mentions: the memory index (a thin router, mostly worth it), a stack of hook-emitted routing tables, and one clear offender, a backlog board injected in full, all 39 items, into every session (21%), most of which are never touched that session. That is the textbook shape of a bad line item, high weight and low read-probability. The cleanest cut: inject a count and today's due items, not the whole list, and reclaim about 1,400 tokens a session at close to zero information loss. The tool sorts pinned tokens by role so you can tell load-bearing context from reference material that just happens to be nailed to the top of the window. The fix is rarely delete, it is move: push reference stuff behind load-on-demand.

## What's still off

It measures weight, not read-probability, so it ranks suspects but cannot prove a block is ignored; that judgement is yours. Token counts are an estimate unless `tiktoken` is importable. It runs your SessionStart hooks, assumed read-only because they usually just echo a file or query a local database; a flag skips them if not. And it counts the file and hook layer you control, not the tool schemas and server instructions the platform injects, which are a separate and larger fight. The lesson holds regardless: before you delete a line of `AGENTS.md` because a benchmark told you it does not pay, weigh your actual tax. The file everyone benchmarks is almost certainly not where your tokens go. Your always-on injections are.

Code: [`code/143-context-tax`](../code/143-context-tax/).
