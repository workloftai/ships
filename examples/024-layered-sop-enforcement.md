# Layered SOP Enforcement: turning checklists into code

**Date:** 2026-06-03
**Author:** Alfred + Bob
**Category:** infra

We had a documented procedure for shipping work, and the agent kept skipping steps in it. The fix was not a sterner prompt. It was to stop trusting the agent to remember and move the hard rules into code that blocks the action when a precondition is missing. The hero image on the published version of this write-up exists because a hook refused to let the article be written without one.

## What we did

Our standard operating procedures lived as documentation: a Ships SOP, voice rules, an order of operations. Documentation is honour-system. The agent read it most of the time and skipped it some of the time, usually the same step under load. The recurring miss was the hero image: every published article is meant to get one, and that was the step quietly dropped when the queue got long.

So we built enforcement in three layers rather than one nag.

- **A hard gate (the load-bearing layer).** A `PreToolUse` hook fires before any file write. If the write is a dated Ship, Note or News article and its hero image is not already on disk, the hook exits with code 2 and the write never happens. There is no bypass flag by design. The only way past it is to generate the hero first, which is exactly the SOP order.
- **A pinned SOP index.** A `SessionStart` hook injects a small routing table into every session, including after context compaction: trigger, governing SOP, hard preconditions, and which of them are hook-enforced. The agent wakes up knowing the rules instead of rediscovering them.
- **A recent-conversation bridge.** A related `SessionStart` hook surfaces the last few exchanges from prior sessions, so a cold start picks up the thread instead of opening blind.

## Why it was worth doing

A prompt that says "always do X" has a non-zero skip rate. A hook that exits 2 when X is missing has a skip rate of zero. That is the whole argument. We moved one rule, every article gets a hero, from "usually" to "always", in about forty lines of Python that fail open on any internal error so a broken gate can never block every write.

The deeper win is the pattern. Once you have one deterministic gate, every other hard precondition becomes a known shape: write the check, wire the hook, delete the honour-system version. The routing table is the index of what is enforced versus what is still on trust, so the gaps are visible rather than assumed closed.

## What's still off

`PreToolUse` hooks do not fire for subagent tool calls, so a write dispatched through a subagent slips the gate. That is acceptable for now because the main session is where we publish, but it is a real hole. The gate is structural, not semantic: it checks the hero file exists, not that it is any good. And only the hero rule is gated so far; the post ledger and homepage banner are still honour-system. We deliberately did not build a full natural-language SOP router or a state-machine orchestrator. For a one-person shop that is over-engineering and a token tax. The principle is to gate the rules that actually got skipped, not every rule that could be.
