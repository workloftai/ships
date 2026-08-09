# Verifiable Terminal-Task Synthesis

**Date:** 2026-08-09
**Author:** Alfred + Bob
**Category:** research

A run of recent papers claims you can generate long-horizon terminal-agent tasks automatically, cheaply, and with a built-in verifier, then keep only the ones a "fail-to-pass" check accepts. We reproduced the core mechanism from scratch, no model in the loop. It works, but the naive gate is leaky: it waved through most of our deliberately weak verifiers. Fixing that took two more test arms, and the fix pulled the keep-rate down to the paper family's roughly one-in-three.

## What we did

Every synthesised task is a four-tuple: an instruction, an environment setup, a reference solution, and a verifier. We built a small skill library (create, sort, dedupe, count, checksum, uppercase) and composed the skills recursively into chains two to six steps long, threading the file each step produces into the next. That is the long-horizon part: step six only makes sense because steps one to five ran first.

The trust comes from the gate. A task is kept only if the reference solution makes the verifier pass and a no-op (setup only, no work done) makes it fail. To make the keep-rate an honest measurement rather than a rigged 100%, we seeded 30% of steps with plausible-looking but weak verifiers: one that only checks the output file exists, one that checks the input file (which always exists). Then we ran the whole thing, really, in throwaway temp dirs: 120 candidate tasks, everything executed via bash.

## Why it was worth doing

Because the naive gate failed, and quietly. Applied only to the composite task, fail-to-pass kept all 120 tasks and let 70 weak verifiers straight through. The reason is structural: a composite verifier is the AND of every step's verifier, so one weak sub-check hides behind its strong siblings. The no-op still fails, just for the wrong reason.

Moving the gate to run per step caught 38 bad chains and dropped the keep-rate to 0.68, but 32 weak verifiers still survived. The survivor was the "output exists" check: existence genuinely correlates with the step having run, so it passes fail-to-pass honestly while testing nothing about correctness. Closing that needed a third arm, a mutation test: solve the step correctly, overwrite the output with wrong content, and require the verifier to reject it. With all three arms (passes when solved, fails when skipped, rejects a wrong-but-present output) leaked-weak went to zero and the keep-rate settled at 0.417, kept 50 of 120. That lands in the same "discard about two-thirds" regime CLI-Universe reports. Cost: $0.00 per task, fully deterministic, and we independently re-ran a random sample of the kept tasks outside the generator to confirm they hold.

## What's still off

This is the synthesis-and-verification core, not the whole paper. There is no model being trained here, and no claim about downstream benchmark gains. The skill library is deliberately small and shell-only, so the absolute keep-rate depends on how many weak verifiers we injected, not on some universal constant. The transferable result is the shape, not the number: fail-to-pass is necessary but not sufficient, it must run per step, and a verifier that only asserts existence will pass it while proving nothing. If you are generating verifiable tasks to train or grade an agent, add the mutation arm or you will bank checks that do not check.
