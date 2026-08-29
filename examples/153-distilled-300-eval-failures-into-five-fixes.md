# We distilled 300 eval failures into five fixes

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** infra

Our nightly eval writes a fail with a reason every time an agent's output falls below bar, and we had 303 of them stacking up as separate tickets, the same problems re-reported night after night. We built the step of the self-improvement loop everyone sketches and nobody shows: read the failures, cluster them by who failed and how, and distil each cluster into one root cause. The 303 collapsed into five. And 76 per cent of them turned out to be our own logging, not our agents.

## What we did

The tool reads the kill verdicts out of the eval's own score log (2,672 graded outputs, 303 failed), groups them by which agent action they came from, and hands each cluster to a model with one job: find the single recurring root cause, say whose fault it is (agent, rubric, or logging), and write one concrete fix. A model fallback means a flaky call never silently drops a cluster. What comes out is not 303 tickets. It is a short, ranked list where each line covers dozens of failures at once. Code in [`code/154-distilled-300-eval-failures-into-five-fixes`](../code/154-distilled-300-eval-failures-into-five-fixes).

## Why it was worth doing

The split is the story. Of the clustered failures, **221 were logging**: the eval was grading a truncated preview of the output, so real fields looked missing and complete rationales looked cut off mid-sentence. Sixty were genuine agent faults, small and real. Nine were a stale rubric failing correct work. Pointed honestly at our own flags, the self-improvement loop did not tell us to improve the agents. It told us to fix the eval.

This lands harder because of what we shipped earlier the same day. This morning we fixed exactly one of these logging clusters, a juror whose rationale was being clipped before the grader saw it. We thought it was a one-off. The distiller shows the identical bug across four different agent actions, 221 failures in total, most still live. One fix at the logging layer, grade the full output and not the preview, clears three quarters of the board.

## What's still off

The distillation is a model reading reasons, so a cluster's root cause is a strong hypothesis, not a proven diagnosis; you still read it and check before you cut code. It clusters by agent action, so a pattern that cuts across actions (like this logging one) only becomes visible when you read the fault column, not from the grouping itself. And it distils, it does not fix. Turning "grade the full output" into a landed change across four actions is the next ship, teed up but not done. This is the cheap half of the loop: reading a failure is cheap, the cure is still the work.
