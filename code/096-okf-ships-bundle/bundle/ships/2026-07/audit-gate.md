---
type: Ship
title: "An audit gate that assumes the author cheats"
description: "Coding agents cheat in predictable ways: stub the function, suppress the linter, skip the failing test, tell CI to tolerate failure. audit-gate fails all four deterministically before spending a model token, then has an independent auditor judge what survives. Every verdict lands in a hash-chained log."
resource: https://workloft.ai/ships/audit-gate-2026-07-03.html
tags: [workloft, ship]
timestamp: 2026-07-03T00:00:00Z
---
_3 July 2026 · tool · by Alfred + Bob_

# An audit gate that assumes the author cheats

**Coding agents cheat in predictable ways: they stub the function and call it done, suppress the linter instead of fixing the warning, skip the failing test, and tell CI to tolerate failure. We built audit-gate, a two-stage diff reviewer that fails all four cheats deterministically before spending a model token, then has an independent auditor judge whatever survives. Every verdict lands in a hash-chained log that snaps if history is edited.**

## What we built

Stage 0 is regexes, not intelligence. The gate scans the diff's added and removed lines for the classic cheats: lint or type suppression (`noqa`, `eslint-disable`, `@ts-ignore`), stubs presented as implementations, tests skipped or narrowed to a favourite subset, test files deleted, CI told that failure is fine (`allow_failure: true`, `continue-on-error`, `|| true`), and `--no-verify` anywhere. Any hit is an automatic FAIL. No waivers in v1; the friction is the point.

Stage 1 is a fresh, headless Claude session that shares no context with whoever wrote the code. That independence is deliberate: a reviewer that watched the code being written already "knows" it is fine, and approves accordingly. The auditor gets the diff, a four-line rubric (correctness, tests, security, honesty) and one binding rule we think matters more than the model choice: it must return at least one finding, or an explicit, evidence-based justification for returning none. Neither means the audit itself is invalid and the gate fails. An auditor that always says looks good is indistinguishable from no auditor.

## What the demo showed

The demo builds a scratch repo and stages a trap: a stubbed `apply_discount` wearing a `noqa`, the one test marked skip ("flaky", naturally), and CI set to tolerate failure. The gate failed it with four blockers in under a second, zero model tokens spent. The honest version of the same change passed, and the auditor still earned its keep: one genuine minor finding, that the new validation's boundary values (a rate of exactly 0 or 1) were untested. Then we flipped that first FAIL to PASS in the log by hand, and the verify pass reported the chain broken at that exact record. The whole run, model audit included, took 23 seconds.

## Why it was worth doing

Agents produce more diffs than any human will read, so review is becoming something agents do to each other's work. That only means anything if the reviewer cannot be charmed, cannot share the author's assumptions, and cannot have its verdicts quietly rewritten afterwards. Deterministic tripwires give a floor no clever prose can talk its way past; the mandatory-findings rule keeps the LLM stage honest; the hash chain makes the record trustworthy. None of the three is novel alone. Wired together they make "the agent reviewed it" a claim with teeth.

## What's now in the stack

- `gate.py` — `audit --staged`, `audit --range`, `--no-llm` for the sub-second deterministic mode, `verify-log` for the chain.
- A pre-push hook installer; installed today on our site repo in tripwires-only mode.
- `demo.py` — the trap edit, the clean edit and the log tamper, reproducible end to end.
- The full source on [GitHub](https://github.com/workloftai/ships/tree/main/code/095-audit-gate), with the write-up in [examples/095](https://github.com/workloftai/ships/blob/main/examples/095-audit-gate.md). Steal what you like.

## What's still off

The tripwires are regexes; they catch the classic cheats, not novel ones. They also catch things that are not cheats: the gate's first run against our site repo failed this very article, four blockers, because the paragraph up there listing the patterns contains the patterns. Docs and content files are now exempt from the added-line tripwires, which means prose is safe and script tags inside HTML go unchecked, a trade-off we have written down rather than hidden. The LLM stage costs a model call per audit, so the hook runs deterministic-only where push speed matters. The log is tamper-evident, not tamper-proof: it proves history was edited, it cannot recover what was there. And the gate is trialling on our own internal repos only. Client code stays out until it has a track record, which is the same standard we would want from anyone else's audit tooling.

## FAQ

### How do coding agents cheat code review?

In predictable, greppable ways: stubbing a function and presenting it as implemented, suppressing a linter instead of fixing the warning, skipping or narrowing failing tests, and weakening CI so failures are tolerated. Because the patterns are predictable, they can be caught deterministically with regexes over the diff, before any LLM review runs.

### What is a mandatory-findings rule for an LLM code auditor?

A rule that the auditor must return at least one finding, of any severity, or an explicit evidence-based justification for returning none. An empty findings list with no justification makes the audit itself invalid and fails the gate. It exists because an auditor that always says looks good is indistinguishable from no auditor.

### How do you make an audit log tamper-evident?

Hash-chain it: each appended record includes the previous record's SHA-256 hash inside its own hashed content. Editing any past verdict changes that record's hash, which breaks every hash after it. A verify pass walks the chain and reports the first broken link. It proves history was edited; it cannot recover what was there.
