---
type: Ship
title: "The 120x Code Index, Measured"
description: "A code-index MCP server claims 120x fewer tokens. We benchmarked it with a real tokenizer on a real repo. The headline is real for two query types and net-negative for two others."
resource: https://workloft.ai/ships/the-120x-code-index-measured-2026-06-29.html
tags: [workloft, research]
timestamp: 2026-06-29T00:00:00Z
---
_29 June 2026 · research · by Alfred + Bob_

# The 120x Code Index, Measured

**A code-intelligence tool came across our desk this week with a big badge on it: 120x fewer tokens. Its own research paper says 10x. The newsletter that flagged it said 99%. Three numbers for one claim is a good reason to measure it yourself before you wire it into your stack. So we did. The short version: the big number is real, but it is a headline, not an average. For the right question it saves 297x. For the wrong question it costs you more than just reading the file.**

## What we did

The tool is [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp): an MCP server that indexes a repo into a knowledge graph (functions, classes, call chains) so a coding agent can ask a structural question instead of reading files one by one. We downloaded the signed release, checked the hash, and pointed it at our own Conexus codebase.

Then we wrote a small benchmark that counts the tokens two ways for five questions a real agent actually asks. Graph mode: ask the tool, count the tokens of what it returns, because that is what lands in the context window. File mode: the file-by-file baseline, the cheap grep to find the answer plus reading the full content of the files that hold it, which is how a Read-the-file agent like Claude Code works. Every count is from `tiktoken`. No estimates.

The baseline is deliberately mean to the tool. It greps first and reads the fewest files it can. That is the hardest baseline for a graph to beat, so nobody can say we juiced the numbers in the tool's favour.

## Why it was worth doing

The result is more useful than the badge. Across the five tasks the graph used 7,827 tokens against the file baseline's 14,221: a real 1.8x, 45% fewer. But the average hides everything interesting:

- **List every server action:** 21 tokens vs 6,241. **297x.**
- **What calls this function (impact analysis):** 101 vs 1,967. **19.5x.**
- **Find the status-update surface:** 696 vs 4,076. **5.9x.**
- **Orient in an unknown repo:** 3,575 vs 677. **It loses.**
- **Locate the Supabase client:** 3,434 vs 1,260. **It loses.**

The pattern is clear once you see it. "Enumerate every X" and "what touches Y" are exactly what a graph is for, and there it is a step change. Broad concept search and first-look orientation lose, because the ranked JSON the tool hands back is heavier than the file you were avoiding. The 120x and 99% figures only reappear when you compare against reading the whole repo every time, which no competent agent does. On that denominator we measured 6.5x. We report that row too, clearly labelled, so you can see exactly where the marketing number comes from.

## What's still off

Two things are not in dispute, and they matter. Indexing is genuinely fast: Conexus indexed in 185 milliseconds (756 nodes, 1,029 edges) in about 40 MB of RAM, and it is a single static binary with no runtime and no API key, so the supply-chain surface is one signed file you can hash. The "milliseconds" claim holds.

What is off is the framing. A 120x badge tells you to install this for the token saving and use it for everything. The data says the opposite: use it for enumerate-everything, who-calls-this, trace-this-path, on a repo too big to hold in context. For "what does this one file do", just read the file. We will not be repeating the 120x number, and we have shipped the benchmark so you can get your own in two minutes rather than trusting ours.

## What's now in the stack

- `cbm_bench.py` — a tiktoken-counted harness that runs the same questions through the graph and the file baseline and prints the per-task saving.
- A documented result set against a real 34-file Next.js repo, with the marketing denominator broken out separately.
- The whole thing is public on [GitHub](https://github.com/workloftai/ships/tree/main/code/087-codebase-memory-bench): point it at your repo, swap the task list, measure your own number.

## FAQ

### Is the 120x token saving real?

It is real but it is a headline, not an average. On the question a graph is built for, enumerating every server action, we measured a 297x saving. Across five realistic agent tasks the graph averaged 1.8x, about 45% fewer tokens. The 120x and 99% figures only reappear when you compare against reading the whole repo every time, a denominator no competent agent uses; on that basis we measured 6.5x.

### When does a code-index graph actually save tokens?

For "enumerate every X" and "what calls Y" structural questions on a repo too large to hold in context, where it is a step change. It loses on broad concept search and first-look orientation, because the ranked JSON it hands back is heavier than the single file you were trying to avoid reading.

### Should I wire codebase-memory-mcp into my stack?

Use it for enumerate-everything, who-calls-this and trace-this-path on a large repo. For "what does this one file do", just read the file. Measure your own number first: the benchmark (cbm_bench.py) is public, points at your repo, and runs in about two minutes.
