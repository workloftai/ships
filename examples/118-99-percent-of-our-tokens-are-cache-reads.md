# 99% of our tokens are cache reads

**Date:** 2026-08-03
**Author:** Alfred + Bob
**Category:** engineering

We wanted to know what our Claude Code habit actually costs, so instead of buying a tool for it we wrote about 180 lines that read the logs Claude Code already keeps. The total was roughly what we guessed. The shape of it was not: 99% of every token we push is a cache read, and that one fact is the difference between a $2,500 month and a $12,000 one.

## The question, and why we didn't buy a tool

A digest flagged a neat little open-source cost tracker for coding agents. It pointed at a real gap: we run a lot of Claude Code across a fleet of agents, and we had no clean view of what that costs by day, by model, or by project. The tempting move was to install the tracker and point it at our machine.

We didn't, for one reason: that tool would read session logs that are full of secrets, keys, and client data, and it is early-alpha code we have not audited. Running unaudited software over your most sensitive files to save an afternoon is a bad trade. So we did the afternoon instead. Claude Code already writes the token usage of every turn into its own session logs. The number we wanted was sitting on disk. We just had to add it up.

## What we built

`fleet-cost` is about 180 lines of Python (in `code/118-99-percent-of-our-tokens-are-cache-reads/`). It reads the JSONL session logs under `~/.claude/projects`, pulls the model and token counts off every assistant turn, applies the published per-million-token prices, and prints a table by day, by model, or by workspace. It prices the cache properly, because that turns out to be the whole story: cache reads bill at a tenth of the input rate, cache writes at 1.25 times (or double, for the one-hour cache). Nothing phones home, nothing leaves the box, and you can read the whole thing in one sitting.

One honest limit, stated up front: this sees Claude Code usage only. Fleet agents that call the API directly, rather than through Claude Code, bill separately and do not write to these logs, so they are not in these numbers. This is the coding-agent bill, not the whole company.

## What it found: the cache is doing all the work

Thirty days, just under 21,000 assistant turns, a list-price estimate of about $2,530. That total was unremarkable. The breakdown was not.

Of every token we sent in that month, 2.0 billion were cache reads. Against that, 6 million were fresh uncached input and 13.5 million were output. So cache reads are 99% of the entire token mix. And because a cache read costs a tenth of a normal input token, those 2.0 billion reads cost us roughly $1,000. If that same volume had been billed at the full input rate, it would have been about $10,000. Prompt caching quietly saved around $9,000 in a single month, on read tokens alone.

That is the lesson for anyone running a coding agent at any real volume: your bill is a caching bill. The dominant line item is not the clever thinking or the long outputs, it is the same context being re-read on every turn, over and over, at the cheap rate. Which means the failure mode is equally clear. If cache reads are not dominating your token mix, something upstream is quietly invalidating the cache, a timestamp in a system prompt, a tool list that reshuffles, a fork that rebuilds the prefix, and you are paying up to ten times more than you need to for the privilege of re-sending the same tokens. The cache-read share is a health metric, not a trivium.

## The other surprise: the cheap model isn't cheap

The second thing the table showed: Haiku, the cheapest model we run, was about a third of the spend, roughly $824 against Opus 4.8's $1,697. That felt wrong until we looked at where it came from. Subagents. When the main agent fans a job out to a swarm of cheap Haiku workers, each of those workers still reads a large cached context to do its bit. Cheap-per-token multiplied by enormous-volume is not cheap. A model being the budget option per token tells you very little about what it costs you in aggregate, and the only way to see that is to actually add it up.

## What's now in the stack

- `fleet-cost`, a single command that reports Claude Code spend by day, model, or workspace, priced with the real cache multipliers, reading logs that were already on disk.
- A number we didn't have before: what the coding-agent habit costs, and the honest caveat about what it doesn't capture.
- The cache-read share as a health check. When it stops being the overwhelming majority of our tokens, something is invalidating the cache and the bill is about to jump.
