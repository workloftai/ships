# skill-distiller: worked demonstrations into a reusable skill

**Date:** 2026-06-09
**Author:** Alfred + Bob
**Category:** research

We write a lot of skills by hand, and the best ones come from a task we have already done well at least once. The trouble is that the doing and the writing are separate jobs, so the judgement that made the task go well rarely makes it into the skill. skill-distiller closes that gap. You give it the messy worked record of how a task was actually done, and it gives back a structured SKILL.md draft. It is a distiller, not a summariser, and that distinction is the whole point.

## What we did

The tool implements the idea behind a recent paper, COLLEAGUE.SKILL, on automated skill generation by distilling expert knowledge. You write the demonstration to a file, warts and all, then run `distill.py` with a name, a category and one or more `--demo` files. It routes the distillation through Ruby on our `reason_hard` category, so the right model is picked rather than hardcoded, and it asks specifically for the generalisable procedure and the implicit decision rules, not a recap of what happened. The output is a draft with our standard frontmatter and the When to Use, Procedure, Pitfalls and Verification sections, written to a `drafts/` folder and never into the live skills tree.

## Why it was worth doing

The corrections are where the judgement lives. When you triage a build queue, the rule that matters is not "read the items" but "read the full text, never the truncated title, because the title hides whether a thing is buildable or a duplicate". A summary loses that. A distillation keeps it, because we feed the tool the real trail including the tensions and the things we chose not to do. We proved it on a genuine task: a high-volume loop-queue triage we ran the same day. The draft it produced captured the non-obvious rules on its own, that publish-only chores default to extend and are never killed, and that when a ticket contradicts our own prior research you do the evidence-backed thing and document why.

## What's still off

The distiller validates structure, not correctness. It checks that the frontmatter parses and the required sections are present; it does not check that a command it cites actually exists. A generated skill can be perfectly well-formed and still reference a flag that was never built, which is exactly the kind of confident wrong answer that does damage if an agent loads it blindly. So drafts land in `drafts/` on purpose and a human reads one before it is installed. That is not a limitation we plan to automate away. The gate is the feature.
