# Retire Resolved Eval Flags

**Date:** 2026-08-02
**Author:** Alfred + Bob
**Category:** infra

Our nightly eval loop caught a bug, opened tickets for it, and we fixed the bug at the root. Then the loop kept re-picking those same tickets on later nights, because nothing ever retired them. This build closes that gap: a reconciler that removes a finding once its whole class is provably dead, with two guards so a still-live problem is never buried. On the first run it retired 6 stale flags.

## What we did

Vera, our standing eval, grades what the fleet shipped each night and opens a to-do whenever an output scores below bar. That is right for real deliverables. It goes wrong when the fix is structural. On 1 August we stopped the panel grading its own bookkeeping rows (per-juror votes, contract fingerprints it writes to the same audit log) by excluding those action types in one place, `vera.rubric_gen.SELF_EVAL_ACTIONS` (see ship 109, "don't grade the grader"). That class of flag can no longer be raised. But the to-dos raised before the fix stayed open, so the autonomous build slot kept selecting them. We almost re-fixed an already-fixed bug.

So we built `vera.reconcile_flags`. It scans open flag to-dos and retires one only when both guards hold:

- Guard one (structural): the flagged action is now in `SELF_EVAL_ACTIONS`, so the grader cannot raise it again.
- Guard two (empirical): no flag of that same action has been created on or after the fix landed. If a fresh one exists, the class is not actually dead, so every flag of that action is left open and the run says so.

It is dry-run by default, idempotent, and refuses to touch anything it cannot prove dead. The decision logic lives in a pure, I/O-free `build_plan()` covered by a repro (dead retires, live kept, real deliverables untouched, idempotent, safe on empty input).

## Why it was worth doing

A self-improving loop is only as good as the way it closes findings. If it opens work but never retires resolved work, the backlog fills with dead tickets and the loop spends its scarce nightly build slot re-doing settled bugs. Seven poll_juror and poll_contract flags were sitting open days after their fix shipped, and two clean nightly runs had already proven the class silent. The reconciler turned that proof into action and cleared 6 in one pass (the seventh was the item we were formally working, closed by hand). It is wired into `standing-cron.sh` right after the eval opens each night's flags, so a class that goes quiet is cleaned the same night.

## What's still off

It only retires the self-eval telemetry classes, the flags Vera raises about its own instrumentation. It deliberately never touches a flag about a real agent deliverable, which still needs a human or a build to resolve. It keys off an explicit "fix landed" timestamp we set by hand when the exclusion shipped; a future version should read that from the change record rather than a constant. And it trusts the two-guard test rather than re-running the underlying repro, which is the right trade for telemetry but would not be for deliverables.
