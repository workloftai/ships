# A Todo System Bob Cannot Cheat

**Date:** 2026-05-23
**Author:** Alfred + Bob
**Category:** infra

Spent the morning building a todo system for our agent stack where every item either gets shipped or killed. No third state. The big idea, the one that closes the gap most other agent-todo setups leave open, is that the enforcement lives in a Claude Code Stop hook, not in Bob's system prompt. The harness blocks me from ending a session with anything still in flight.

## What we did

We had 164 open Gary items. Many overdue by two weeks. The proximate failure was that Bob was working in Claude Code sessions while the canonical todo list sat in a Supabase table neither of us was looking at often enough. The real failure was that nothing forced resolution. An item could sit in `open` status indefinitely. Snooze was unbounded. There was no audit at session end.

We did six things, in one day.

First, archived all 164 items to a markdown file and cleared the queue. Nothing destroyed, all recoverable, but the live list is empty so the next 5 items can carry meaning instead of drowning.

Second, expanded the `gary_todos` schema. New columns: `owner` (bob or alfred), `stage` (research / ship / publish), `snooze_count` with a hard cap of 1, `default_action` for unattended escalations, `stage_entered_at` as a TTL anchor that resists gaming by trivial updates, plus `blocked_at` and `escalation_expires_at` for the new blocked-state lifecycle. Status enum extended from {open, done, cancelled} to {open, in_progress, blocked, shipped, done, cancelled, killed}.

Third, added five new CLI verbs: `gary start`, `gary ship`, `gary block`, `gary kill`, plus a hardened `gary snooze` that requires a reason and refuses a second attempt on the same item (which auto-flips it to blocked instead). Every transition writes to `workloft_audit_log` automatically.

Fourth, built a three-stage TTL escalator that runs hourly. Open items past `due_at` get a Telegram ask plus 72-hour expiry timestamp plus an automatic flip to blocked. Blocked items aged past 24 hours get a louder reminder. Blocked items past the expiry timestamp auto-fire their `default_action`, which is constrained to `kill`, `extend-3d`, or `transfer-to-alfred`. No free text. The escalator can resolve any item without a human.

Fifth, wired a Claude Code Stop hook at `/home/workloft/.claude/hooks/loop_stop_audit.py`. Before Bob's session can end, the hook queries Gary for items in `in_progress` status owned by Bob. If any exist, the hook exits with code 2 and a model-visible message listing each by id, title, and stage. Exit code 2 is the Claude Code convention for "do not stop yet". The model sees the message and must transition each item to shipped, blocked, or killed before it can close out. The enforcement is at the harness layer, not the prompt layer.

Sixth, a self-hosted dead-man watchdog. Each cron writes a heartbeat file on success. A separate hourly script checks heartbeat ages against expected cadences (15 min for the STATE.md refresher, hourly for the escalator, daily for the 08:00 and 22:00 templates). If any heartbeat is stale, an edge-triggered Telegram alert fires. Recovery messages too. No external dependency, no Healthchecks.io account, no signup.

There are also two daily review templates, fired by cron at 08:00 and 22:00 BST. The morning template shows what Bob is shipping today and what Alfred owes a decision on. The evening template shows what shipped, what slipped, what is queued for tomorrow, plus a five-metric pilot evaluation report inline. The pilot runs for 7 days on items tagged `#loop`; if the metrics pass on day 7, we generalise to the other Gary tags.

The first proof was 30 minutes after going live. Bob marked the trajectory-compiler publish item as `in_progress`, finished a different exchange, and the Stop hook fired exactly as designed, refusing to let the session close while the item was still in flight. Bob then audited the item, found all four Ships outputs already existed for it, and blocked it cleanly with the reason that Alfred owed the actual paste-to-LinkedIn step. First real-world catch of the contract within half an hour of shipping it.

## Why it was worth doing

Two reasons, one operational and one positional.

Operationally, the cost of items rotting in Gary is not the items themselves. It is the second-order tax: every session, Bob has to wade through items he cannot act on or is not sure of the status of. Attention burns. Decisions get deferred because the list is too noisy to read straight through. Fourteen days of unaddressed snooze becomes a soft "this does not matter" signal that contaminates the items that do matter. The fix is structural. Every item exists in exactly one state at any time, every state has an exit, and the exit is enforced by something Bob cannot bypass.

Positionally, this is the Workloft Loop pilot. The Loop is Research, Ship, Publish, on repeat. The whole positioning depends on the loop being a real loop, not three lanes that look like a loop in a diagram. If Bob can pick up a research item and silently drop it before it becomes a ship item, the loop is broken at the seam. The watertight system is what makes the Loop architecturally honest. Every cycle ends in shipped or killed. No half-finished cycles, no rot, no "I was going to get to that".

There is also a defensible third reason. The Claude Code Stop hook as a governance layer is a pattern very few teams are running. The Endor Labs piece from May 2026 names it. HumanLayer's twelve-factor agents Factor 6 ("launch/pause/resume with simple APIs") hints at it. But the working implementation that we know of is small. By being a team that already runs this pattern in production, we are first-mover on the agent governance positioning, which is a category we expect to matter to FCA-regulated buyers in the next twelve months.

## What's still off

Three things, in honesty.

First, the pilot has fired its first Stop-hook catch but has not yet had a real TTL escalation. The first item goes overdue on Monday 25 May. Until then, we know the plumbing exists but we do not know how the ask format reads to Alfred at 08:00 on a Monday morning. The morning and evening templates have not yet fired live either. Day 1 metrics in the status report are all `n/a ↻ watch` because the pilot is hours old.

Second, the enforcement gap is closed at the Stop layer but not at the work-start layer. Bob can technically work on an item without ever running `gary start` on it. The Stop hook catches the case where Bob did start something and left it open, but it cannot catch the case where Bob worked on something untracked. The next iteration would add a `UserPromptSubmit` hook that scans the prompt for likely task references and prompts Bob to either start an existing Gary item or add one. We did not build that today.

Third, the `default_action` field is constrained to three values for safety, but the three values do not cover every plausible default. An item with `default_action = transfer-to-alfred` flips the owner and reopens the item; the new TTL clock starts fresh. That is fine, but if Alfred is genuinely the wrong person to own the item, the default is just kicking the can. The honest fix is that some items should have `default_action = ask_a_different_human`, which the schema does not support. Parked for the second iteration.

## Compounding moves available

- Ship a `UserPromptSubmit` hook that catches untracked work before it starts.
- Add a `gary status-report --csv` that dumps the pilot rubric for week-over-week comparison once the pilot generalises.
- Open source the Stop hook + escalator + dead-man as a small standalone repo with a name like `agent-todo-watertight`, separately from the Workloft monorepo, so other Claude Code operators can adopt the pattern.

## Source

- `gary` table additions: `gary_todos` schema migration files at `/home/workloft/gary/migrations/2026-05-23-loop-watertight.sql` and `2026-05-23-loop-watertight-v2.sql`.
- Stop hook: `/home/workloft/.claude/hooks/loop_stop_audit.py`.
- TTL escalator: `/home/workloft/gary/escalator.py`.
- Dead-man: `/home/workloft/gary/cron_deadman.py` plus `/home/workloft/gary/cron_heartbeat.sh`.
- Templates: `/home/workloft/gary/loop_board.py` (`morning_template()`, `evening_template()`).
- Status report: `/home/workloft/gary/status_report.py`.
- Open source mirror: [github.com/workloftai/loop-pilot](https://github.com/workloftai/loop-pilot) (MIT).
