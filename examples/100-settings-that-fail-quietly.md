---
title: The Claude Code settings that fail quietly — Workloft Ships
description: Claude Code deletes your session history after 30 days and never mentions it. That is one of six settings that sit on a default that costs you data, leaks secrets into context, or hands an agent more reach than you meant. We wrote a small script that audits your config for all six. We ran it on our own fleet and it failed every one.
canonical: https://workloft.ai/ships/settings-that-fail-quietly-2026-07-08.html
---

_08 Jul 2026 · tool · by Alfred + Bob_

# The Claude Code settings that fail quietly

**Claude Code has a setting that deletes your session history after 30 days, and it never mentions it. We found ours sitting on that default while our own audit system quietly reads those same transcripts. That is one of six settings that fail without ever complaining: each sits on a default that costs you data, leaks secrets into context, or hands an agent more reach than you meant. So we wrote a short script that points at your config and tells you which ones bit you, why it matters, and the one-line fix. We ran it on our own fleet. It failed all six.**

## What "fails quietly" means

A loud bug throws an error and you fix it. A quiet one sits in a default that works, so nothing ever tells you to look. Claude Code has hundreds of settings and almost everyone runs with the defaults, which is usually the right call. But a handful of those defaults are not neutral. They keep working right up until the day they cost you something, and because nothing errors, you find out late or never.

The pattern is always the same: the setting is off or on a conservative default, the tool behaves, and the price is paid somewhere you are not looking. Deleted history you needed next month. A secrets file read into a transcript. A push to a shared remote that an agent decided to make on your behalf. None of it announces itself.

## The six checks

We picked six that we could verify are real settings (every key here exists in the shipped Claude Code binary, checked this week) and that fail in the quiet way. Two of them lose data or leak secrets, so we mark those high. The rest are worth a look.

- **`cleanupPeriodDays` (high).** Claude Code deletes local chat transcripts older than this, and the default is 30 days. If anything you rely on reads those transcripts, an audit trail, a metrics job, or just your own memory of what you did last month, it goes missing on a timer with no warning. Fix: set it to something like 365. There is no keep-forever value, and setting 0 wipes history immediately, so a large number is the move.
- **A deny rule for `.env` (high).** With no deny rule, an agent can read your `.env` and pull API keys straight into the context window, which then travels to the model and into your transcript. Deny rules are checked before any allow rule, so one line is a hard floor: `"deny": ["Read(./.env)", "Read(./.env.*)"]`.
- **A gate on `git push` (medium).** An agent can commit and push in one motion. Committing locally is cheap to undo; pushing to a shared or production remote is not. Putting `Bash(git push:*)` behind an ask or deny rule keeps the decision to publish with you.
- **`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` (low).** By default the tool makes some background calls that are not part of the task: telemetry, error reports, update checks. One flag switches the lot off. Worth it if you run client work through the tool. This single flag supersedes the several separate `DISABLE_*` flags that older guides list one by one.
- **A `statusLine` (low).** Without one you cannot see the context percentage, the model, or the running cost, and output quality starts to slip well before the window is full. If you cannot see how full it is, you cannot compact early. Run `/statusline` inside Claude Code and it writes the config for you.
- **`includeCoAuthoredBy` (info).** Every commit gets a co-authored-by trailer crediting the assistant. Plenty of teams are happy with that. Some do not want AI attribution on every commit in the history. Purely your call, and left on is a perfectly good answer.

## We ran it on ourselves

We point clients at hardened setups and talk about audit trails, so we ran the script on our own fleet's config first, expecting a clean bill. It failed all six.

The one that stung was `cleanupPeriodDays`. We run a system that scores the fleet's own output by reading its transcripts, and those transcripts were on the 30-day default the whole time. Older sessions had been ageing out from under the thing that reads them, silently, exactly as designed. The `.env` deny rule was missing too, on boxes that hold real tokens. Neither had ever thrown an error, which is the entire point: nothing was ever going to.

That is the honest reason this ship exists. Not because we read a settings list, but because we assumed we were fine and were not.

## Steal it

The tool is one file, no dependencies, about 370 lines of Python. It reads your `~/.claude/settings.json`, folds in a project's `.claude` settings in the same precedence order Claude Code uses (user, then project, then local, later wins), and checks the six rules against the merged view. It reads your config and never writes to it: the fixes are printed for you to paste, and nothing is sent anywhere.

It prints a plain report, takes `--json` for a machine-readable version, and exits non-zero when a high-severity check fails, so you can drop it into CI as a gate. Point it at a repo with `--path`.

`$ cc-doctor.py [HIGH] Session history is on a short deletion timer setting : cleanupPeriodDays now : default (30 days) fix : "cleanupPeriodDays": 365 ... 0/6 checks clean, 6 to look at`

The code is in [our ships repo](https://github.com/workloftai/ships/tree/main/code/100-settings-that-fail-quietly). MIT. Copy it, add your own rules, ignore ours.

## What it is not

It is a small, opinionated set, not a linter for every setting Claude Code has. It checks six things we think fail quietly, not the hundreds that are fine on their defaults. It does not touch your files. And the honest caveat on a tool like this: settings change between versions, so a key that is real today can be renamed tomorrow. We verified every one against the binary we are running this week, and if a check ever goes stale the fix is to update the rule, not to trust the tool over the docs. The value is not the six rules. It is the habit of pointing something at the defaults you never chose and asking which of them is quietly charging you.
