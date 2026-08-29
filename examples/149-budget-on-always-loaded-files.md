# We put a budget on our always-loaded files

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** infra

A handful of files get loaded into an agent's context on every single session: the project instructions, the house rules, the memory index. They only ever grow. You add a rule here, a pointer there, and each edit is far too small to notice, so nobody ever notices. One day you are paying a few hundred tokens of tax on every turn for guidance the model half-reads. We built a gauge for it. The first thing it did was catch our own memory index, 19 tokens over its budget, carrying an 811-token block that was supposed to live somewhere else.

## What we did

It is a Claude Code hook, about 150 lines, no dependencies. It runs after any write or edit, and if the file is one of the always-loaded ones (`CLAUDE.md`, `AGENTS.md`, the memory `MEMORY.md`), it estimates the token size and compares it to a budget. Under budget, silent. Over, it surfaces a short warning naming the largest sections and points you at a rules directory to move them into. It never blocks the edit and never moves anything on its own. It is a gauge, not a gate.

The same script runs as a command line tool, so you can audit a file on demand, and an opt-in `--apply` extracts the single biggest section into `.claude/rules/`, leaves a one-line pointer behind, and writes a backup first. Code in [`code/150-budget-on-always-loaded-files`](../code/150-budget-on-always-loaded-files).

## Why it was worth doing

Context bloat is invisible precisely because it is incremental. No single edit is the problem, the accumulation is, and there is no natural moment where you total it up. The write is that moment, and it costs nothing to check there. When we pointed the gauge at our own setup it did exactly what it was meant to: our memory root index, the one we had told ourselves to keep thin at forty lines, had crept to fifty-five, and the gauge fingered the exact section that had drifted. We knew the rule. We were quietly breaking it. The tool is the thing that says so out loud.

## What's still off

The token count is an estimate, four characters to a token, not a real tokeniser. Close enough for a gauge, wrong for an invoice. It matches files by name, so the watch list is configured, not discovered. The `--apply` extraction is conservative on purpose: it moves one section and stops, because deciding what an always-loaded file should say is a judgement, not a byte count. And a budget is a heuristic, not a law. Sometimes the context earns its tokens and the right move is to raise the number, not gut the file. The gauge tells you where you are. It does not tell you that you are wrong.
