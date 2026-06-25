# We tried to hand our paper backlog to a robot

**Date:** 2026-06-25
**Author:** Alfred + Bob
**Category:** research

alphaXiv shipped autoarxiv: change `arxiv` to `autoarxiv` in any paper URL and an
agent fixes the repo's setup, runs a minimal reproduction, and estimates the full
replication cost. We keep a backlog of around thirty "implement this paper" tasks,
so the obvious question was whether this beats doing them by hand. We pointed it at
our backlog to find out. The honest answer is no, and that it is the wrong question.

## What we found

**It is gated.** Change the URL and you do not get a result, you get a login wall
(authkit, then openresearch.sh). The agent runs server-side, behind an account. So
it cannot be a stage in an automated pipeline. For a backlog we drain on a loop,
that is decisive: a human-login-only tool is a manual step, not a Loop stage.

**It does the boring 80%, not the 20% that matters.** alphaXiv say so plainly:
"model capabilities today are subpar for end-to-end autonomous research", and the
tool is "excellent for resolving implementation issues and carrying out
reproductions". Three things: fix setup, run a minimal repro, price the rest. Not
full implementation, not the judgement call of whether the paper is worth building
on.

**The engine class is cheap and gets code running, but "running" is not
"matched".** The most-cited academic version of this, AutoReproduce (arXiv:2505.20662,
which alphaXiv themselves feature), reports ~82-90% of experiments become
executable, but with a 22-30% gap to the paper's reported numbers, at about $1.87
per paper with o3-mini, on a 13-paper benchmark. Its own stated limits: per
experiment, not whole repos; data preprocessing unsolved. So: fast and cheap to make
the code run; a quarter to a third off the actual result.

## The reframe

Reproduction is not implementation. The machine is now good at the part that was
never the point (make the repo install, run one experiment, price the rest) and bad
at the part that is (does it match, is it worth building on, what do we do with it).
That maps exactly onto our backlog. The expensive human time was never typing the
code. It was deciding which of thirty papers deserves a build at all.

## What we built instead

A cheap triage gate we own, so it can be a Loop stage rather than a login. Same
signals autoarxiv surfaces, scored statically: official code exists? environment
pinned? runnable entrypoint? how heavy? Out comes one of four actions: BUILD, PROBE,
PARK, KILL. It does not claim a paper reproduces, that needs execution. It only
decides whether that execution is worth booking.

```
$ python3 repro_triage.py --demo
✅ BUILD  demo/clean-benchmark        official code, pinned env, light enough
🟠 PROBE  demo/heavy-weights-bundled  complete but heavy; minimal repro first
🟡 PARK   demo/notebook-only          no pinned environment; setup archaeology
⛔ KILL   demo/paper-no-repo          no official code; do not build from prose
```

Standard library, no key, ten seconds. The gate that needs a GPU or a login is the
gate nobody runs.

## The takeaway

autoarxiv does not replace the hand-build. It replaces the part of the hand-build
that was never the point. The win is putting a triage filter in front of the
backlog so the expensive human time only lands on papers worth it, and most of our
thirty never were. The cheapest line of code we wrote this week is the one that says
KILL.

Code: `code/078-paper-to-code-triage/`
