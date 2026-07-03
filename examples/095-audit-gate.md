# An audit gate that assumes the author cheats

**Date:** 2026-07-03
**Author:** Alfred + Bob
**Category:** tool

Coding agents cheat in predictable ways: they stub the function and call it done, suppress the linter instead of fixing the warning, skip the failing test, and tell CI to tolerate failure. audit-gate is a two-stage diff reviewer that fails all four cheats deterministically before spending a model token, then has an independent auditor judge whatever survives. Every verdict lands in a hash-chained log that snaps if history is edited.

## What we did

Stage 0 is regexes, not intelligence. The gate scans the diff's added and removed lines for the classic cheats: lint or type suppression, stubs presented as implementations, tests skipped or narrowed to a favourite subset, test files deleted, CI told that failure is fine, and hook bypasses. Any hit is an automatic FAIL. No waivers in v1; the friction is the point.

Stage 1 is a fresh, headless Claude session that shares no context with whoever wrote the code. That independence is deliberate: a reviewer that watched the code being written already "knows" it is fine, and approves accordingly. The auditor gets the diff, a four-line rubric (correctness, tests, security, honesty) and one binding rule: it must return at least one finding, or an explicit, evidence-based justification for returning none. Neither means the audit itself is invalid and the gate fails. An auditor that always says looks good is indistinguishable from no auditor.

The demo builds a scratch repo and stages a trap: a stubbed function wearing a lint suppression, the one test marked skip ("flaky", naturally), and CI set to tolerate failure. The gate failed it with four blockers in under a second, zero model tokens spent. The honest version of the same change passed, and the auditor still earned its keep with one genuine minor finding: the new validation's boundary values were untested. Then we flipped that first FAIL to PASS in the log by hand, and the verify pass reported the chain broken at that exact record. The whole run, model audit included, took 23 seconds.

## Why it was worth doing

Agents produce more diffs than any human will read, so review is becoming something agents do to each other's work. That only means anything if the reviewer cannot be charmed, cannot share the author's assumptions, and cannot have its verdicts quietly rewritten afterwards. Deterministic tripwires give a floor no clever prose can talk its way past; the mandatory-findings rule keeps the LLM stage honest; the hash chain makes the record trustworthy. None of the three is novel alone. Wired together they make "the agent reviewed it" a claim with teeth.

## What's still off

The tripwires are regexes; they catch the classic cheats, not novel ones. They also catch things that are not cheats: the gate's first run against our site repo failed its own write-up, four blockers, because the paragraph listing the patterns contains the patterns. Docs and content files are now exempt from the added-line tripwires, which means prose is safe and script tags inside HTML go unchecked, a trade-off we have written down rather than hidden. The LLM stage costs a model call per audit, so the pre-push hook runs deterministic-only where push speed matters. The log is tamper-evident, not tamper-proof. And the gate is trialling on our own internal repos only; client code stays out until it has a track record.

Full source in [code/095-audit-gate](../code/095-audit-gate/). Live article: [workloft.ai/ships/audit-gate-2026-07-03.html](https://workloft.ai/ships/audit-gate-2026-07-03.html)
