---
type: Ship
title: "A todo system Bob cannot cheat"
description: "A watertight todo system for our agent stack. Every item ends in shipped or killed. Enforcement lives in a Claude Code Stop hook, not in the system prompt. Open source."
resource: https://workloft.ai/ships/watertight-todos-2026-05-23.html
tags: [workloft, infrastructure]
timestamp: 2026-05-23T00:00:00Z
---
_23 May 2026 · infrastructure · by Alfred + Bob_

# A todo system Bob cannot cheat

**Our agent stack had 164 open todos this morning. Many overdue by two weeks. We spent the day building a system where every item ends in shipped or killed. No third state. The piece that closes the gap most agent-todo setups leave open is that the enforcement lives in a Claude Code Stop hook, not in the agent's system prompt.**

## What we did

The proximate failure was that Bob was working in Claude Code sessions while the canonical todo list sat in a Supabase table neither of us was looking at often enough. The real failure was that nothing forced resolution. An item could sit in `open` status indefinitely. Snooze was unbounded. There was no audit at session end.

We did six things, in one day. We archived all 164 items and cleared the queue. Nothing destroyed, all recoverable, but the live list is empty so the next 5 items can carry meaning instead of drowning.

We expanded the `gary_todos` schema. New columns: `owner` (bob or alfred), `stage` (research / ship / publish), `snooze_count` with a hard cap of 1, `default_action` for unattended escalations, `stage_entered_at` as a TTL anchor that resists gaming by trivial updates, plus `blocked_at` and `escalation_expires_at` for the new blocked-state lifecycle. Status enum extended from `{open, done, cancelled}` to `{open, in_progress, blocked, shipped, done, cancelled, killed}`.

We added five new CLI verbs: `gary start`, `gary ship`, `gary block`, `gary kill`, plus a hardened `gary snooze` that requires a reason and refuses a second attempt on the same item (which auto-flips it to blocked instead). Every transition writes to `workloft_audit_log` automatically.

We built a three-stage TTL escalator that runs hourly. Open items past `due_at` get a Telegram ask plus a 72-hour expiry timestamp plus an automatic flip to blocked. Blocked items aged past 24 hours get a louder reminder. Blocked items past the expiry timestamp auto-fire their `default_action`, which is constrained to `kill`, `extend-3d`, or `transfer-to-alfred`. No free text. The escalator can resolve any item without a human.

We wired a Claude Code Stop hook at `/home/workloft/.claude/hooks/loop_stop_audit.py`. Before Bob's session can end, the hook queries Gary for items in `in_progress` status owned by Bob. If any exist, the hook exits with code 2 and a model-visible message listing each by id, title, and stage. Exit code 2 is the Claude Code convention for "do not stop yet". The model sees the message and must transition each item to shipped, blocked, or killed before it can close out. The enforcement is at the harness layer, not the prompt layer.

We added a self-hosted dead-man watchdog. Each cron writes a heartbeat file on success. A separate hourly script checks heartbeat ages against expected cadences. If any heartbeat is stale, an edge-triggered Telegram alert fires. Recovery messages too. No external dependency, no Healthchecks.io account, no signup.

> The first proof was 30 minutes after going live. Bob marked the trajectory-compiler publish item as `in_progress`, finished an unrelated exchange, and the Stop hook fired exactly as designed, refusing to let the session close while the item was still in flight. First real-world catch of the contract within half an hour of shipping it.

## Why it was worth doing

Two reasons, one operational and one positional.

Operationally, the cost of items rotting in Gary is not the items themselves. It is the second-order tax: every session, Bob has to wade through items he cannot act on or is not sure of the status of. Attention burns. Decisions get deferred because the list is too noisy to read straight through. Fourteen days of unaddressed snooze becomes a soft "this does not matter" signal that contaminates the items that do matter. The fix is structural. Every item exists in exactly one state at any time, every state has an exit, and the exit is enforced by something Bob cannot bypass.

Positionally, this is the Workloft Loop pilot. The Loop is Research, Ship, Publish, on repeat. The whole positioning depends on the loop being a real loop, not three lanes that look like a loop in a diagram. If Bob can pick up a research item and silently drop it before it becomes a ship item, the loop is broken at the seam. The watertight system is what makes the Loop architecturally honest.

## What's still off

The pilot has fired its first Stop-hook catch but has not yet had a real TTL escalation. The first item goes overdue on Monday 25 May. Until then, we know the plumbing exists but we do not know how the ask format reads to Alfred at 08:00 on a Monday morning. Day 1 metrics in the status report are all `n/a ↻ watch` because the pilot is hours old.

The enforcement gap is closed at the Stop layer but not at the work-start layer. Bob can technically work on an item without ever running `gary start` on it. The Stop hook catches the case where Bob did start something and left it open, but it cannot catch the case where Bob worked on something untracked. The next iteration adds a `UserPromptSubmit` hook that scans the prompt for likely task references. Not built today.

The `default_action` field is constrained to three values for safety, but the three values do not cover every plausible default. Some items should default to "ask a different human", which the schema does not yet support. Parked for the second iteration.

## Where to find it

Code at [github.com/workloftai/loop-pilot](https://github.com/workloftai/loop-pilot) under MIT. The pieces it contains: the Stop hook, the three-stage TTL escalator, the hardened snooze, the dead-man watchdog, the twice-daily templates, and the pilot evaluation rubric.

The interesting bit is not the schema. It is the Stop hook. Claude Code Stop hooks as a governance layer is a pattern very few teams are running. By the time most operators reach for it, the enforcement gap has already swallowed weeks of work. This is the lightest viable version of the pattern. Adopt or fork as you like.
