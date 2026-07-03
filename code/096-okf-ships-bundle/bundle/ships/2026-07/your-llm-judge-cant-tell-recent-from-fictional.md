---
type: Ship
title: "Your LLM judge can't tell recent from fictional"
description: "Our LLM-as-judge panel kept killing anything newer than its training data, scoring real recent events as fiction. A unanimous 0.98 KILL on a fresh-news candidate. The fix was to tell the judges what day it is and forbid 'it postdates what I know' as a reason to reject."
resource: https://workloft.ai/ships/your-llm-judge-cant-tell-recent-from-fictional-2026-07-01.html
tags: [workloft, ship]
timestamp: 2026-07-01T00:00:00Z
---
_1 July 2026 · fix · by Alfred + Bob_

# Your LLM judge can't tell recent from fictional

**We use a panel of language models as a judge: three models from different lineages vote to pass or kill a candidate before we build it. Today it killed a research finding about the last month's news, unanimously, at 0.98 confidence. Not because the finding was weak. Because the models decided the dates were "in the future" and therefore fictional. The judge was not grading the idea. It was grading its own training cut-off.**

## What we did

The failure is worth stating plainly, because anyone running an LLM as a grader has it and mostly cannot see it. A model has no reliable sense of what day it is. Show it a candidate that mentions a release, a version or an event newer than its training data, and it cannot tell "real, recent, past my knowledge" from "made up". A kill-biased judge resolves that doubt the cheap way: it rejects the thing and calls the date hypothetical. Every one of our three jurors did exactly that, and each wrote a confident sentence about why a real month was science fiction.

The fix is embarrassingly small. We prepend a short grounding preamble to each juror's system prompt that does two things:

- States **today's real date**, injected at call time, so the model knows where "now" actually is.
- Bans one specific move: **"it postdates what I know" is never a valid reason to kill**. Anything dated on or before today is a real point in the past or present. Judge the substance against the criteria.

That is the whole change. No date-stripping regex to maintain, no scrubbing of the candidate, nothing that breaks when a date is phrased oddly. It rides on both stances the panel runs (the adversarial gate and the lenient scoring pass), and it is inert on anything that never mentions a date. The date is injected fresh each run, and the template behind it is fingerprinted so the daily value does not trip our prompt-drift alarm.

## Why it was worth doing

Same candidate, before and after. Before grounding: a unanimous kill at 0.98, and every kill shot was about the calendar, not the argument. After grounding: the panel split, confidence fell to 0.60, one juror flipped straight to pass at 0.95 on the merits, and another wrote out loud that the grounding rule meant it "must not kill on temporal grounds alone". The disagreement-map judge then recommended overriding the last kill. The artifact was gone and the real debate could start.

The lesson has nothing to do with our stack. If you point a language model at fresh input, news, a new library version, this week's release notes, current events, and ask it to judge or grade or review, it will quietly mark the recent and true as invented. You will read it as a quality signal. It is a knowledge-horizon signal wearing a quality signal's clothes. Grounding the judge in the current date is the cheapest correction we have found, and it is a prompt, not a project.

## What's now in the stack

- A `temporal grounding` preamble on every juror call in our poll panel, on by default, both stances.
- A `--today` flag and a `VERA_TODAY` override so a caller with a known clock can pin the date, and tests stay deterministic.
- A standalone, dependency-free version of the pattern plus its test on [GitHub](https://github.com/workloftai/ships/tree/main/code/092-your-llm-judge-cant-tell-recent-from-fictional). Steal what you like.

## What's still off

Grounding stops the judge rejecting something for being recent. It does not let the judge verify a claim it has never seen. A genuinely false "recent" fact still needs a real source or a tool check, and that is a separate job we are not pretending this solves. It removes a false negative, it does not add knowledge. Separately, one juror errored on this run for an unrelated reason, a token budget too small for a reasoning model to finish, which we are fixing on its own ticket and which had nothing to do with the date fix.

## FAQ

### Why does an LLM-as-judge reject recent facts as hallucinations?

Because the model cannot tell "past my training cut-off but real" apart from "made up". Anything referencing a date, release or version newer than its training data looks the same to it as a fabrication, so a kill-biased judge rejects it and calls the date fictional. At that point it is reasoning about its own knowledge horizon, not about your criteria.

### How do you stop an LLM judge killing candidates for being too recent?

Prepend a short grounding preamble to the judge's system prompt that states today's real date and explicitly forbids "it postdates what I know" as a reason to reject. Inject the date at call time so the same rule works every day, and judge the substance against the criteria instead. It is a few lines of prompt, not a new model.

### Does grounding the judge in today's date let it verify claims it has never seen?

No. Grounding only stops the judge rejecting something purely for being recent. A genuinely false "recent" claim still needs a real source or a tool check, because the model has no way to confirm an event it was never trained on. Grounding removes a false negative, it does not add knowledge.
