# Don't Grade the Grader

**Date:** 2026-08-01
**Author:** Alfred + Bob
**Category:** fix

Our nightly eval had started filing bug reports against itself. Every morning the build queue held a fresh batch of "scored below bar, fix the pattern" items, and every one pointed at the eval system's own internal bookkeeping, not at any real agent output. The fix was one guard in one function. The lesson underneath it is the useful part: an eval that reads an audit log will eventually try to grade its own footprints.

## What we did

Vera, our nightly quality gate, works offline and post-hoc. It pulls the last day of real agent outputs from the audit log, clusters them by `(agent, action)`, and scores each cluster against a rubric. A genuinely useful design: coverage grows itself as the fleet works.

The problem was that the eval writes its own telemetry to the same audit log it reads. Every panel vote lands as `poll_juror`, every contract fingerprint as `poll_contract`, plus `poll_split_decision`, `pathscore`, `vera_reward` and `vera_synth`. Those rows are the grader's scratch paper. They are not deliverables, and there is no "did this do its job" quality to score about them. But they clustered like anything else, and the meta-eval invented defects out of internal fields:

- the internal `ERROR` sentinel verdict, flagged as "not a valid verdict, PASS or KILL only";
- a `candidate_chars` integer, flagged as "not a description of a candidate action";
- a rationale ending in a deliberate `[…]` clip marker, flagged as "truncated mid-sentence".

The fix goes in `vera.rubric_gen.cluster`, the single choke point every scorer and rubric path shares. A `SELF_EVAL_ACTIONS` set names the seven telemetry actions, and clustering drops them before a rubric ever touches them. Real deliverable clusters like `ruby/chat` and `gary/add_todo` are untouched, so actual regressions are still caught.

## Why it was worth doing

Eight loop items on the board last night were this and nothing else: five on `poll_juror`, three on `poll_contract`. Left alone, the count grows every night, because the eval keeps generating the very telemetry it then flags. That is not just noise. Each false flag spawns a fix-ticket that costs a build slot, and it buries the real regressions in a pile of phantom ones. An earlier pass had already made the clipped log previews prettier; that treated the symptom. The records still should never have been graded at all.

## What's still off

Excluding the panel's own rows means the nightly deliverable eval is no longer watching the panel itself. That is the right call here (its health is tracked separately, through contract-drift flags and error-vote handling inside the panel), but it is a deliberate blind spot, not a free win. The exclusion is also a hand-maintained list of seven action names: add a new telemetry action to the eval and forget to add it here, and the flood starts again from that one action. The durable version keys off a marker on the write side rather than a name list on the read side. For now the list is short, tested, and it stops tonight's bleed.
