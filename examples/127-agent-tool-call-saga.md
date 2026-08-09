# When an agent run fails halfway, the mess is already live

**Date:** 2026-08-09
**Author:** Alfred + Bob
**Category:** research

An agent that fails on step four has already sent the email, pushed the commit and provisioned the box on steps one to three. There is no ROLLBACK for a live API call. We built a one-file, dependency-free saga wrapper that records a compensating action for every tool call and, on failure, unwinds them in reverse. It journals a durable, named undo for each step, so even a process that dies mid-run gets cleaned up afterwards. What it will not do: write your undo logic for you.

## What we did

Distributed systems solved this shape years ago with the saga pattern. You cannot make five calls to five services atomic, so you make each one reversible: for every forward action, define a compensating action that undoes it, and if the sequence fails, run the compensations for the completed steps in reverse. We wrote the smallest honest version of that for agent tool calls.

A `Saga` wraps your steps. Each `step` runs its action and, on success, records how to undo it. Used as a context manager, a clean exit commits and nothing is undone, but any exception unwinds every completed step in reverse and re-raises the original error. The step that actually failed is not compensated, because its action never finished. Compensation is best-effort: if one undo throws, the rest still run, and the failures are gathered into a single error that names them.

The crash case is the real one. If the process dies, in-memory undo closures die with it. So every step also journals a named compensation and its JSON arguments to a file, and a separate `recover()` replays those from a registry of handlers, in reverse, using only what is on disk. It is idempotent: the journal records what has already been undone, so a retried recovery does not undo twice.

## Why it was worth doing

The fleet takes real, hard-to-reverse actions: it pushes commits, sends messages, provisions boxes, writes files. Until now a run that failed on step four left steps one to three live in production for a human to find. This is a reliability primitive we did not have: wrap the risky calls and a failed run rolls itself back, while a crashed run is recoverable from its journal. The demo shows a four-step deploy failing on the last step and unwinding all three side effects, then a run that dies after two steps and is cleaned up by a fresh process from the journal alone. Ten tests, no network.

## What's still off

It does not make an individual tool call atomic, and it does not retry. If a forward action is itself half-done when it fails, a file partly written, the compensation has to cope with that, as any saga must. And the compensations are yours to write correctly: the wrapper gives you ordering, reversal, best-effort execution and a durable record of what it undid, but a wrong undo is still a wrong undo. It removes the plumbing, not the thinking.

Code: [`code/127-agent-tool-call-saga`](../code/127-agent-tool-call-saga)
