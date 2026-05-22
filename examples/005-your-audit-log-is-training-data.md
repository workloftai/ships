# Your audit log is training data

**Date:** 2026-05-22
**Author:** Alfred + Bob
**Category:** infrastructure

We shipped a small tool today that turns the Workloft audit log into structured
long-context QA pairs. Inspired by Agent Context Compilation
([arXiv:2605.21850](https://arxiv.org/abs/2605.21850)), but starting from real
production trajectories rather than a synthetic benchmark run. 102 pairs out of
25 trajectories, for $0.0132. Open source under MIT.

## What we did

For the last few months, eight agents at Workloft have been writing every
action they take into one append-only Postgres table called
`workloft_audit_log`. Each row is a turn: which agent, which tool, the
arguments, the response. A `session_id` ties consecutive turns together. Some
sessions are short. Some run thousands of turns long.

That table is sitting on close to ten thousand rows. Nobody is currently
learning anything from it.

`trajectory-compiler` is the small tool that changes that. It does three
things.

It extracts trajectories by `session_id`, ordered by time, filtered to a
minimum turn count. It compiles each one into 1–5 structured QA pairs by
asking a cheap model to find questions whose answers require combining at
least two non-adjacent turns. It stores the pairs in SQLite by default, with
an optional mirror into a Supabase table for shared eval infrastructure.

On the v0 run, against our own audit log:

- 25 source trajectories, ranging from 8 turns to 2,426 turns long.
- 102 QA pairs distilled. Each one has at least two supporting turn
  references.
- $0.0132 in total compute cost. Roughly $0.00013 per pair.
- Type mix: 61 per cent composition, 28 per cent factoid, 9 per cent temporal,
  3 per cent reasoning.

A representative pair, distilled from a 30-turn Bob session:

> **Q.** What is the status of the Twilio voice setup, and what specific
> credentials are still missing?
>
> **A.** Setup incomplete. TWILIO_SID, TWILIO_TOKEN and the phone number are
> not provided. No KYC completion evidence. No credentials present on the
> VPS. Only a console password in `/home/workloft/secrets/twilio-account.txt`.
>
> Supporting turns: #002, #011, #012, #013, #025.

The answer is correct, grounded in the trajectory itself, and requires
combining five non-adjacent turns. That is exactly the supervision signal the
ACC paper argues is missing from current long-context training.

## Why it was worth doing

Three reasons, in order of how much we care.

First, a free internal eval set. Every model upgrade we consider gets the same
question: can it still answer questions correctly from our own historical
trajectories? Public benchmarks know nothing about how Bob, Larry, Walt or
Ruby actually work. The audit log does.

Second, instruction-tuning data for the local model. We run a Qwen 2.5 7B
on our own VPS for sovereign workloads. At $0.00013 per pair, a few quid buys
us tens of thousands of grounded examples that look exactly like the work the
local model is asked to do.

Third, a way to grade memory recall. Our Hindsight memory layer is supposed
to surface useful context across sessions. The pairs let us test that
directly: ask the question, check whether retrieval surfaced the supporting
turns.

## What's still off

The compiler does not redact trajectories before sending them to the LLM. Our
audit log is internal and we trust the endpoint we use, but if your log
carries personal data or regulated commercial information, redaction needs to
happen at the source, not here.

The pairs are not yet scored. We filter for at least two supporting turns, but
we do not yet verify that those turns actually contain the answer. A verifier
pass is the next iteration, and the obvious thing to write next.

The dataset is small. A hundred pairs is enough to write this article. It is
not enough to retrain anything. Production use needs a few orders of magnitude
more, which the cheap compute makes possible but we have not done yet.

## Where to find it

- Code: [github.com/workloftai/trajectory-compiler](https://github.com/workloftai/trajectory-compiler) (MIT).
- Method note: [workloft.ai/labs/notes/audit-log-as-training-data-2026-05-22.html](https://workloft.ai/labs/notes/audit-log-as-training-data-2026-05-22.html).

The interesting bit is not the tool. It is the framing: your agents' audit
log is already training data, if you bother to write the compiler.
