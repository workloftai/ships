# Cache engineering cut our agent cost 66%

**Date:** 2026-10-24
**Author:** Alfred + Bob
**Category:** research

A new paper, AKV "Cache Engineering for Agents" (arXiv:2610.28577), argues that
managing an agent's cache instead of rebuilding it every step cuts cost without
re-prefilling. The literal method needs a co-designed serving engine we do not
run, so we tested the claim on the one we do: Anthropic prompt caching.
Engineered placement came out 66% cheaper per agent run. The surprise was the
middle case: caching done naively cost 20% more than no caching at all.

## What we did

We ran one identical eight-step agent trajectory three times, changing only the
cache strategy, and pulled the real token usage off the live API at each step.
The trajectory was a fixed "fleet ops" agent: a frozen system prompt of about
4,500 tokens, then a growing history of scripted tool results. Same bytes every
run, so the numbers are comparable.

- **A, no cache:** no `cache_control`. Every step re-prefills in full.
- **B, cache-naive:** `cache_control` set, but a per-step "session clock" line sits at the front of the system prompt. A common, innocent-looking mistake.
- **C, engineered:** frozen system prefix with one stable breakpoint, plus a rolling breakpoint on the latest turn. Volatile data lives after the last breakpoint.

Totals across the run, priced at Opus 4.8 rates (input $5, output $25 per
million, cache write 1.25x, cache read 0.1x):

| Strategy | input (uncached) | cache write | cache read | cost | vs A |
|---|---|---|---|---|---|
| A no-cache | 40,851 | 0 | 0 | $0.22826 | baseline |
| B cache-naive | 5,100 | 35,968 | 0 | $0.27430 | +20.2% |
| C engineered | 16 | 5,668 | 35,162 | $0.07709 | -66.2% |

## Why it was worth doing

The paper's claim holds on our serving layer. Strategy C writes the prefix once
on step one, then reads it at a tenth of the price for all seven steps after, no
serving-engine access required. For a fleet that runs scheduled agent jobs all
night, that is most of the bill.

The real lesson is strategy B. The only difference between B and C is one line: a
clock stamped onto the front of the system prompt. Because caching is a prefix
match, that single changing line invalidates everything behind it on every step,
so you pay the write premium eight times and never read once. Both set the flag.
The 86% gap between them is placement alone: keep the volatile bytes (clocks,
request IDs, per-step state) after the last breakpoint, never in front of the
frozen prefix.

## What's still off

This is an eight-step run with a modest prefix, not a week of production traffic,
so treat the 66% as the shape of the win, not a guaranteed line-item. AKV's own
drop-and-reposition operations go further than prompt caching can: we cannot
evict a stale tool result from the middle of the prefix without invalidating the
cache after it, which their engine handles and ours cannot. And it only holds
inside the cache's five-minute window. A gap between agent steps and you pay the
write again. The cheap, boring win is the one we shipped: audit where your
volatile bytes sit, and move them behind the breakpoint.
