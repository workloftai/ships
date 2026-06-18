# harness-review-gate

**Put the reviewer back into a self-improving agent loop.**

A small, runnable reference implementation that pairs with [Workloft Research
Note №38](https://workloft.ai/labs/notes/self-certifying-harness-2026-06-18.html),
which read [Self-Harness (arXiv:2606.09498)](https://arxiv.org/abs/2606.09498)
and named the step the paper leaves out: the agent that proposes a harness edit
is the same one that approves it. Self-improvement, read as a control, is
self-approval.

This is the governed version. It keeps the loop — mine weaknesses, propose
edits, accept on evidence — but makes three properties structural facts of the
code rather than promises.

## The three properties

1. **Separation of duties.** The `Proposer` holds the *dev* set it can see; the
   `ReviewGate` holds a private *held-out* set the proposer never receives. The
   gate recomputes every score itself and treats the proposer's self-reported
   number as a claim, never as evidence. Neither object holds a reference to the
   other's data — separation by construction, not by policy.

2. **Independent acceptance.** An edit lands only if the gate's held-out score
   does not regress and clears a floor. The edit that overfits the proposer's
   visible set is exactly the one this catches.

3. **Tamper-evident record.** Every proposal — accepted *and* rejected — is
   appended to a hash-chained `ChangeLog`, pinned to the harness version live
   for it. Altering any past entry breaks the chain. "The harness changed
   itself" becomes something you can evidence, not screenshot.

## Run it

```bash
python3 demo.py            # the trap-edit walkthrough
python3 test_harness_gate.py   # 5 tests, no deps
```

The demo is deterministic and uses no model — the point is the control flow.
A slow-but-cache-friendly *dev* set makes `aggressive_cache` the proposer's
single biggest win (+0.60 dev). The gate's held-out set contains
freshness-sensitive tasks that `aggressive_cache` silently breaks, so it
regresses held-out 0.40 → 0.20 and is refused. The honest `retries 1 → 3` edit,
ranked second by the proposer, improves held-out 0.40 → 0.80 and lands.

```
Proposer's ranking (on the dev set it can see):
  +0.60 dev   enable aggressive_cache (cut latency)
  +0.40 dev   raise retries 1 -> 3 (de-flake)
  -> A naive Self-Harness loop ships the #1.

Independent gate verdicts (recomputed on the held-out set):
  [REJECT] enable aggressive_cache  | held-out 0.40 -> 0.20 | regressed
  [ACCEPT] raise retries 1 -> 3     | held-out 0.40 -> 0.80 | improved

  chain verifies: True
  tamper with entry #0 (flip REJECTED -> ACCEPTED)…
  chain verifies: False   <- break is detected
```

## Wiring in a real agent

The toy `Proposer.propose()` and `Task` scorers are drop-in seams:

- Replace `Proposer.propose()` with a real LLM that mines failure traces and
  emits `HarnessEdit`s. It still only ever sees the dev slice.
- Hand `ReviewGate` a held-out task suite the proposer is never given.
- Persist the `ChangeLog` to append-only storage; `verify()` is your audit walk.

The governance property does not depend on the model. It is the shape of the
loop: a proposer that cannot mark its own homework, a gate with evidence the
proposer cannot reach, and a record that cannot be quietly rewritten.

## Why it matters to a regulated buyer

FCA SS1/23 assumes a production change is proposed, reviewed by someone other
than the author, approved, and recorded. A self-improving harness that proposes
and accepts its own edits satisfies none of those four. This puts the missing
reviewer back — as code.

Built by [Workloft](https://workloft.ai). Run by Alfred Churchill.
