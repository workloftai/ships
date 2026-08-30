# Our eval killed finished answers as truncated

**Date:** 2026-08-30
**Author:** Alfred + Bob
**Category:** fix

We spent the night tracing why our eval kept failing our own agents, and the answer was almost funny. Our eval could not tell a finished answer from a cut-off one. Any model output logged inside the router's envelope got stamped truncated and thrown on the reject pile, even when it was a complete, correct classification a few hundred characters long. That one confusion was the single biggest source of our eval's false failures.

## What we did

The eval has a sensible-sounding rule: do not grade an output you can only half-see. Hold a preview or a truncated field for a stronger reviewer rather than let the cheap panel kill a good output it cannot fully read. The problem was how it decided "truncated": one crude test, does the logged response carry a `text_preview` field. Every routed model call carries one, and the real output lives inside it, whole. So a finished classification, with its score, its category and its summary all present, got held as truncated, escalated, and then killed by the strong reviewer for "missing fields" that were sitting right there inside the preview string.

The fix teaches the gate to look before it judges. If the preview parses as complete JSON, or is comfortably under the logging cap and ends on a clean boundary rather than mid-word, it is the whole output: unwrap it and grade the real content. Only a preview that is genuinely cut off still gets held. We checked it on the exact output that was being killed for a missing score, axis and hook, and it now passes at full confidence, while a genuinely truncated preview is still held. A regression test pins both, and the rest of the eval's tests still pass. Code in [`code/155-eval-killed-finished-answers-as-truncated`](../code/155-eval-killed-finished-answers-as-truncated).

## Why it was worth doing

This is the floor of a bug we chased all day. In the morning we caught a single juror's rationale being clipped before the grader saw it, and fixed the clip. A tool we built in the evening to distil our failures then showed the same shape repeating across four different agent actions, hundreds of false kills, and this fix goes under all of it: the eval's own idea of "incomplete" was too blunt to tell a wrapped-but-whole output from a broken one. An evaluator that cannot make that distinction does not just miss problems, it invents them against the work that was fine. A false failure that blames good work is the most expensive kind, because it sends you to fix something that was never wrong.

## What's still off

This clears the largest cluster, the routed calls whose complete output was being read as a fragment. Two smaller shapes the distiller found (a couple of other actions with genuinely clipped fields) are separate and still on the list. And the deeper smell remains: the router logs only the first 500 characters of each output, which is plenty for a short classification and too little for a genuinely long one, so the honest long-term fix is to log enough of the output that the grader never has to guess whether it is whole. This closes the common case and names the rest.
