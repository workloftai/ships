# Two of our slash-commands were fighting over the same trigger

**Date:** 2026-08-25
**Author:** Alfred + Bob
**Category:** infra

We have 27 skills and slash-commands in our agent's setup, built up over months. Each one is a tidy file that does one job well. The problem is not in any of those files. It is in the space between them: `/linkedin` and `/linkedinpost` both answer to a bare `/linkedin`, and which one wins was never something we decided. Nobody lints for that, because the collision does not exist in any single file. So we built the thing that does.

## The bug that lives between files

A skill or slash-command is a trigger plus an instruction. On its own it is easy to reason about. The trouble starts when you have dozens, because two of them can quietly claim overlapping ground: the same slash prefix, the same quoted phrase, the same topic. When you type the trigger, one fires and the other does not, and you rarely notice the one that lost. Reviewing a single skill file will never surface this, because the conflict is a property of the set, not the file.

## What we built

`skill_lint.py` is one stdlib-only, read-only file. It reads every skill and command definition, pulls out what each one claims to trigger on, and ranks the pairs most likely to collide. It scores four signals, strongest first: a **name-prefix** clash where one command name is a prefix of another; a **shared trigger phrase** where two skills quote the same natural-language cue; a **shared slash-token** where both reference the same command; and **lexical overlap**, how much two descriptions lean on the same words, as a proxy for topic overlap. It never writes anything.

## It caught its own bug first, again

The first run reported 68 collisions, which is not a finding, it is noise. The scanner was reading absolute file paths in the skill bodies, `/home` and `/workloft` and `/conexus`, as if they were slash-commands. The fix was to teach the slash matcher the difference between a command and a path segment. The count dropped from 68 to five. Worse, a stray "not the" (part of "NOT the Workloft company page") was being read as a declaration that two skills were deliberately distinct, which downgraded the one collision that actually mattered. We tightened that so a relationship only counts when it names the other skill.

## What it found on us

```
severity  score  pair
----------------------------------------------------------------
HIGH      66     /linkedin  x  /linkedinpost
            - name 'linkedin' is a prefix of 'linkedinpost', so a bare slash is ambiguous
            - lexical overlap 18% on: first-person, linkedin, personal, playbook
MED       35     /go  x  /linkedinpost
LOW       16     /pizza  x  /sourdough
            - lexical overlap 26% on: dough, fermentation, hydration, advice
LOW       13     /repo-status  x  /standup
LOW       12     /ask-larry  x  /screenshot-website
```

The `/linkedin` versus `/linkedinpost` clash is real: one is for personal build-in-public posts, the other for day-job takes, and a bare `/linkedin` could reasonably mean either. Below it, `/pizza` and `/sourdough` lean on the same words because they are both about dough; they are neighbours, not a bug, and the tool ranks them low for exactly that reason. What we were most pleased not to see: `/ahfu` and `/triage`, which are heavy overlaps, did not appear at all, because one explicitly says it is an alias of the other and the linter respects a declared relationship instead of nagging.

## Then we pointed it at the plugins

Run with `--all` it also reads plugin and marketplace skills you did not write but which can still shadow yours. On our machine that pulled in 74 definitions and immediately flagged a real one at the maximum score: three separate channel plugins each ship a `/configure` and an `/access` skill with almost identical descriptions, 87% lexical overlap and the same quoted trigger phrases.

## What it does not do

It measures overlap, not intent. It reads what a skill says it triggers on, not what the model actually picks at dispatch time, so it hands you a shortlist to review, not a verdict. Lexical overlap is a heuristic, not semantics. The point is that the most common bug in a mature agent setup is invisible one file at a time, and five minutes of a read-only script makes it visible.

The linter is one stdlib-only file, MIT-licensed, in [`code/144-skill-collision-linter`](../code/144-skill-collision-linter).
