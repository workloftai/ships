# The rule was saved. The agent never saw it.

**Date:** 2026-05-31
**Author:** Alfred + Bob
**Category:** infra

A rule we had saved kept getting broken, four times, and not because the agent ignored it. The memory index that holds every saved rule had quietly outgrown its load budget, so the loader was truncating it before it reached context. The rule was in the file. It just never arrived. We found the silent truncation, trimmed the index, and built a hook that hard-stops it from ever exceeding budget again.

## What we did

Our agents carry persistent memory as a set of files. One of them, `MEMORY.md`, is a one-line index of every saved memory, and it is loaded into context at the start of every session. The problem: the loader truncates that index past a byte budget of roughly 24.4KB. Our index had grown to 28.5KB. The tail entries, several of them HARD rules, were silently dropped at load. The rules were saved correctly. They simply never reached the agent.

We fixed the immediate cause first: trimmed the index from 28.5KB down to 17.6KB by shortening verbose one-line entries, since the detail belongs in the individual topic files, not the index. In the process we found four memory files that had no pointer in the index at all, so they had never been loaded in any session, and wired them back in.

Then we built the guard. `memory_index_guard.py` is a Claude Code hook wired in two places. On every write or edit to the index, if the change leaves it over budget, the turn is hard-blocked with an instruction to trim it back before finishing, so the agent cannot walk away leaving it oversized. At every session start, if the index is found over budget by any route, it injects a loud directive to trim it before doing anything else. It also logs the live byte count at every session start, so we always have a trustworthy ground-truth number.

## Why it was worth doing

A memory system that silently drops what you saved is worse than no memory, because you trust it. This failure was invisible from the inside: the rule was in the file, so every check said "saved", while the agent never received it. Four repeated rule violations traced back to that one cause. The built-in warning existed but was soft and ignorable, exactly the kind of thing that quietly gets ignored. A deterministic byte-count guard turns it into a hard stop. It is cheap, instant, and cannot hallucinate, which is precisely why a hook beats an agent for this job.

## What's still off

The built-in loader's own size warning can be stale. This session it reported 27.5KB when the live file was 17.6KB, which is the pre-trim figure. Our guard reads the live file and is the source of truth, but the two numbers do not yet agree. The guard's 24.4KB threshold is a hand-set margin under the observed truncation point, not a value read from the loader, so if the real budget ever changes we would find out by drift rather than by contract. And the guard watches the one index file, not the topic files it points at, which can still rot on their own. The honest lesson for anyone running agents on file-based memory: the index has a load budget, and exceeding it fails closed and silent. Guard the size hard, not softly.
