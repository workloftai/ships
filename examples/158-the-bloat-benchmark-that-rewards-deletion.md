# The bloat benchmark that rewards deletion

**Date:** 2026-10-21
**Author:** Alfred + Bob
**Category:** research

A new benchmark, Parsimony, measures how much code an AI agent adds by counting syntax units instead of lines. The idea is right: solve-rate benchmarks do not punish excess code, which is what makes an agent-written codebase expensive to live with. We reproduced the metric faithfully, ran it over 316 of our own AI-generated commits, then showed where it misleads. Ranking agents by net units prefers a comment-free one-liner over a readable fix, and hands first place to a patch that only deletes code and fixes nothing.

## What we did

Parsimony counts "coding units" from a patch: a statement, a call, an attribute access, a comparison, a name, a literal, plus one unit at the end of every block. Punctuation, brackets, comments and formatting do not count, so cramming code onto fewer lines earns no reward. The headline number is net units, added minus deleted.

We rebuilt the counter from the method notes as a standalone Python AST walker, 90 lines, no dependencies. It self-verifies against the author's own calibration: `if x.count(y) > 0: foo(a, b)` is 12 units, and our counter returns exactly 12 before it will run anything else. For a whole file, units after minus units before is exactly added minus deleted, so per-commit net units need no diff algorithm, only a parse of each side.

We then pointed it at real history: 400 commits from one agent repo (306 touched implementation Python), plus a second repo, 316 commits in total. Median net change was 28 units a commit. The mean was pulled to 259 by a single 15,458-unit commit, the usual long tail. And 7 percent of commits were net-negative: the agent removed more than it added.

## Why it was worth doing

Because the metric breaks in two ways that matter, and we can now show each with a live count rather than an opinion.

- **It prefers the code you would not want to keep.** One function written two ways with identical behaviour: a readable version with five guard clauses (33 units) and a single nested ternary crammed onto one line (21 units). Parsimony scores the one-liner 36 percent "better". The readable one loses.
- **It rewards deletion.** A patch that rips out a working loop and returns a wrong constant drops a function from 17 units to 5, a net of minus 12. On a net-units leaderboard that non-fix posts the best score on the board. The author flags this caveat himself; we just made it concrete.

The signal is real but one-directional. Less code is good when behaviour holds, and actively bad when it does not. The number alone cannot tell the two apart.

## What's still off

Net units measures size, not readability or design. The top of the HN thread said the same: the leanest model on the board writes code many would call unmaintainable, while a chattier one spends its units on comments and tests. The author's own data shows models that write more code also solve more tasks (Spearman 0.33 to 0.60), so you cannot chase a low score without watching solve-rate fall with it.

Our take: adopt the direction, not the ranking. We will track net units per agent commit as a secondary maintainability signal, always paired with whether the task still passes and a readability check such as cyclomatic complexity. We will not rank one agent above another on units alone. A benchmark that a delete-everything patch wins is measuring the wrong thing on its own.
