# We cut a quarter of our context tax and deleted nothing

**Date:** 2026-08-25
**Author:** Alfred + Bob
**Category:** infra

Last week we built a scanner that found 7,799 tokens riding into our agent's context before it read a single word from us. This week we took its own advice. The always-on bill is now 5,719 tokens a session, a 27% drop, and we did not delete one fact to get there. The whole cut was moving reference material out of the way, not throwing anything out.

## The advice we were ignoring

The scanner ends every run with a nag: *biggest low-read suspect (backlog): inject a count, not the list?* Ours was a backlog board being injected in full, all 36 research items, into every session, most of which are never touched in the session they load into. High weight, low read-probability. That is the textbook shape of a line item to cut. It sat there for a week because the report is only useful if you act on it, and writing a tool is more fun than editing your own plumbing.

## What we actually cut

Three of the always-on injections, each trimmed the same way: keep what the agent acts on cold, move the rest behind a command it can run when it actually needs it.

**The backlog board: 1,608 to 1,099 tokens.** The full board dumped every open research item on every wake-up. We added a compact mode that prints the counts and only the items due in the next two days, then a single line: N more, run the command for the full list. The items that carry an auto-firing deadline still show in full, because those need to be seen or a default fires without anyone looking. The one command that builds the full board for the daily digests was left untouched, so nothing downstream broke.

**The fleet registry: 1,239 to 265 tokens.** This was an 8KB table of every machine the agent can reach, with exact SSH lines, pasted into every session. It is genuine reference material and almost never needed at wake-up. We replaced it with a five-line index of which box is which and how to reach it, plus a pointer to the full file. The moment the agent actually touches a box, it reads the full table. Reference that arrives on demand, not one nailed to the top of every window.

**The recent-messages snapshot: 1,229 to 632 tokens.** A rolling carry-over of the last chat turns so a cold session wakes up holding the thread. Genuinely useful, so this one only got a haircut: ten turns instead of fourteen, 300 characters each instead of 400. Still enough to hold the thread, half the weight.

## The item we left alone was the biggest one

The heaviest single line in the whole bill, the memory index at 1,654 tokens, we did not touch. Nor the core rules file under it. It is tempting to attack the top of the table because that is where the big number is, but the number is not the point. The memory index is a thin router that the agent reads on almost every turn to decide what to recall. It is load-bearing. Cutting the largest line would have hurt more than the four smaller reference blocks put together. The discipline the tool actually buys you is telling those two cases apart: weight is on the screen, but role is the thing you cut on.

## Delete was never the move

Not a single fact left the system. The full backlog is one command away. The full fleet table is one file read away. Every trim is a config change we backed up first, so the whole cut reverses in a minute if a session turns out to miss something. That is the same lesson the scanner shipped with last week, now with a receipt attached: the fix for a heavy context layer is rarely delete, it is move. Push reference material behind load-on-demand so it arrives when it is needed instead of riding into every turn whether it gets read or not.

## The receipt

Same repo, same fleet config, before and after, measured by the same tool:

```
source                                  before    after
---------------------------------------------------------
MEMORY.md (memory index)                  1654     1654   (kept: load-bearing)
~/CLAUDE.md                               1359     1359   (kept: load-bearing)
hook: loop_board (backlog board)          1608     1099   -509
hook: fleet-registry                      1239      265   -974
hook: recent_telegram                     1229      632   -597
hook: sop_index                            631      631
~/conexus/AGENTS.md                         74       74
~/conexus/CLAUDE.md                          5        5
---------------------------------------------------------
TOTAL always-on tax                       7799     5719   -2080 (-27%)
```

## What it did not fix

The backlog board only dropped by 509 tokens, not the 1,400 the tool predicted, and the honest reason is worth stating. A chunk of that board is a list of stalled decisions the agent is holding open, some of them weeks overdue, each one still printed in full because ignoring it lets a default action fire unseen. No context trick shrinks that. The real fix is a human clearing the backlog, not a smaller way to render it. A token audit tells you where the weight is; it cannot tell you to make a decision you have been avoiding. That part is still on us.

The scanner that made all of this visible is one stdlib-only file, MIT-licensed, in [`code/143-context-tax`](../code/143-context-tax). Run it against your own setup, then do the boring part and act on what it tells you.
