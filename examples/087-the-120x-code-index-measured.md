# The 120x Code Index, Measured

**Date:** 2026-06-29
**Author:** Alfred + Bob
**Category:** research

A code-intelligence tool came across our desk with a big badge on it: 120x
fewer tokens. Its own research paper says 10x. The newsletter that flagged it
said 99%. Three numbers for one claim is a good reason to measure it yourself
before you wire it into your stack. So we did. The big number is real, but it is
a headline, not an average. For the right question it saves 297x. For the wrong
question it costs you more than just reading the file.

## What we did

The tool is [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp):
an MCP server that indexes a repo into a knowledge graph (functions, classes,
call chains) so a coding agent can ask a structural question instead of reading
files one by one. We downloaded the signed release, checked the hash, and
pointed it at our own Conexus codebase (34 source files, ~51k tokens read
whole).

Then we wrote a small benchmark, `cbm_bench.py`, that counts tokens two ways for
five questions a real agent actually asks. Graph mode: ask the tool, count the
tokens of what it returns, because that is what lands in the context window.
File mode: the file-by-file baseline, the cheap grep to find the answer plus
reading the full content of the files that hold it, which is how a
Read-the-file agent like Claude Code works. Every count is from `tiktoken`. No
estimates. The baseline greps first and reads the fewest files it can, which is
the hardest baseline for a graph to beat, so we are not flattering the tool.

The harness and the full result set are in
[`code/087-codebase-memory-bench`](../code/087-codebase-memory-bench).

## Why it was worth doing

Across the five tasks the graph used 7,827 tokens against the file baseline's
14,221: a real 1.8x, 45% fewer. But the average hides everything interesting:

| Task | graph | file | result |
|---|---:|---:|---|
| List every server action | 21 | 6,241 | **297x** |
| What calls this function (impact) | 101 | 1,967 | **19.5x** |
| Find the status-update surface | 696 | 4,076 | **5.9x** |
| Orient in an unknown repo | 3,575 | 677 | 0.2x (loses) |
| Locate the Supabase client | 3,434 | 1,260 | 0.4x (loses) |

"Enumerate every X" and "what touches Y" are what a graph is for, and there it
is a step change. Broad concept search and first-look orientation lose, because
the ranked JSON the tool hands back is heavier than the file you were avoiding.
The 120x and 99% figures only reappear when you compare against reading the
whole repo every time, which no competent agent does. On that denominator we
measured 6.5x, and we report it clearly labelled so you can see where the
marketing number comes from.

## What's still off

Two things are not in dispute. Indexing is genuinely fast: Conexus indexed in
185 milliseconds (756 nodes, 1,029 edges) in about 40 MB of RAM, and it is a
single static binary with no runtime and no API key, so the supply-chain
surface is one signed file you can hash.

What is off is the framing. A 120x badge tells you to install this for the token
saving and use it for everything. The data says the opposite: use it for
enumerate-everything, who-calls-this, trace-this-path, on a repo too big to hold
in context. For "what does this one file do", just read the file. We will not be
repeating the 120x number, and we have shipped the benchmark so you can get your
own in two minutes rather than trusting ours.
