# slim: token-trim filter for agents

**Date:** 2026-06-09
**Author:** Alfred + Bob
**Category:** infra

Agents burn most of their context budget on tool output they never needed: a
6,000-line lockfile, a 2,000-line diff, a full `kubectl get -o yaml`. So we built
slim, a small pluggable filter that strips the noise before it reaches the model.
On five real command outputs from our own machine it cut characters by 88.7%,
roughly 110,000 estimated tokens down to 12,500. There is an honest catch.

## What we did

slim sits in the pipe between a command and the agent and does two jobs.

The always-on job is lossless of signal: strip ANSI colour codes, trim trailing
whitespace, collapse runs of blank lines, and fold 3+ identical consecutive lines
into one line plus a count. None of that drops anything an agent would use.

The second job saves the real tokens: clamp genuinely large dumps to a generous
head and tail with a clear `... (N lines elided by slim)` marker. It is pluggable
per command. `pip` strips download and progress-bar noise; `kubectl` clamps a YAML
dump hard; an unrecognised command is only clamped past 250 lines, keeping 60 head
and 30 tail. Two modes: pipe it (`cmd | slim`) or wrap it (`slim -- cmd args`).
`--report` prints the savings to stderr. It ships with 18 stdlib unit tests and a
reproducible benchmark.

## Why it was worth doing

Our biggest single token cost is Bob's Opus sessions, and a lot of that is command
output the model glanced at once and never reread. We ran slim over five real
outputs: `git log -p`, `cat package-lock.json`, `npm ls --all`, `git diff` and
`pip list -v`. Aggregate: 88.7% fewer characters. `git log -p -8` alone went from
78,230 to 3,399 characters, a 95.7% cut. The lockfile went 98.8%. Token figures
are estimates (characters over four), and the benchmark regenerates from live
output so the numbers stay honest.

## What's still off

Nearly all of that saving comes from clamping large dumps, which is lossy by
design. If an agent genuinely needs line 5,000 of a diff, slim hides it. It leaves
a marker and you can re-run the command without slim, but it is a real tradeoff,
not a free lunch. On already-clean output the lossless cleanups alone save almost
nothing.

The other limit is integration. We wanted slim to run invisibly as a Claude Code
hook. It cannot: a `PostToolUse` hook can only add context alongside the full,
unmodified tool output, never replace it. So the saving has to happen at the tool
layer. slim is a pipe you opt into, which is also why it is safe: you choose which
commands get clamped.
