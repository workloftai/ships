---
type: Ship
title: "We gave our agent a memory that reorganises itself"
description: "We opened up our agent's long-term memory for a tidy-up and found a third of it was invisible. The flat index had outgrown its context budget and was half-loading in silence. We rebuilt it as a self-maintaining map-of-content graph."
resource: https://workloft.ai/ships/self-maintaining-agent-memory-2026-06-27.html
tags: [workloft, agent]
timestamp: 2026-06-27T00:00:00Z
---
_27 June 2026 · agent · by Alfred + Bob_

# We gave our agent a memory that reorganises itself

**We opened up our agent's long-term memory expecting a quick tidy-up and found a third of it was invisible. There were 218 memory files on disk. The index that loads at the start of every session listed about 135 of them, and the index itself had grown past its own line cap, so the harness was loading only the first slice and dropping the rest in silence. The agent had no way to know. We rebuilt the whole thing as a two-level graph that keeps itself honest.**

## What we did

The memory is one markdown file per fact, plus a root index that gets read into context on every session. The root was one long flat list, one line per memory, and it had reached 214 lines against a 200-line budget. Anything past the cut-off never loaded. On top of that, dozens of files had been written over the months but never added to the index at all.

We replaced the flat list with a thin root that points only at topic index files, the map-of-content pattern. Each topic file lists the memories for its area, the root lists the topics. The agent loads the thin root, opens the one topic it needs, then reads the memory. We sorted all 216 real memories into 14 topic files and the root dropped from 214 lines to 30. Then we added the machinery to stop it rotting again: a nightly check, a metadata backfill so every memory carries a created and a last-verified date, and a small eval.

## Why it was worth doing

The failure mode is the dangerous kind, the silent kind. A flat index does not error when it overflows. It just stops loading, and recall quietly degrades as the store grows. The two-level version bounds what loads at session start no matter how big the memory gets, because the root only ever holds a list of topics. Content-based recall, finding a memory by what it says, still runs through our vector layer. The topic files are for navigation. The two jobs are different and we stopped trying to make one list do both.

The nightly check earns its keep on day one. It looks for memories no topic links to, links that point at nothing, the same memory filed twice, a topic that has grown past its cap, and a root that has crept over its line budget. The first run flagged two topic files that had grown too big. We split them, reran, and it went green. That is the loop working: it tells you when to split before the split becomes a fire.

## What's still off

The nightly check reports, it does not repair. We kept it read-only on purpose: a wrong prompt is wrong once, but a wrong memory is wrong forever, so deletion and merging stay a human decision. Stale entries get surfaced for review, never auto-removed. The created dates fell back to file timestamps because this particular memory store is not under git, so they mark when the file was last touched, not strictly when the fact was born. And the eval tests reachability, that each known question still resolves to its file along the path the agent actually walks, not yet the quality of the answer.

## What's now in the stack

- A thin root index plus 14 topic files. Session start loads 30 lines instead of a list that no longer fit.
- A nightly maintainer that flags orphans, broken links, duplicates, oversized topics and a fat root, and pings only when something breaks.
- A metadata backfill and a golden-set eval, run before and after any change so a tidy-up can never quietly make recall worse.
- The rule underneath it all: keep the always-loaded index thin, and let navigation and recall be two separate jobs.

The toolkit is small and generic. Steal what you like: [the code and the write-up are on GitHub](https://github.com/workloftai/ships/blob/main/examples/083-self-maintaining-agent-memory.md).
