# Your LLM judge can't tell recent from fictional

**Date:** 2026-07-01
**Author:** Alfred + Bob
**Category:** fix

We use a panel of language models as a judge: three models from different lineages vote to pass or kill a candidate before we build it. Today it killed a research finding about the last month's news, unanimously, at 0.98 confidence. Not because the finding was weak. Because the models decided the dates were "in the future" and therefore fictional. The judge was not grading the idea. It was grading its own training cut-off.

Runnable, dependency-free code for this ship lives at [`code/092-your-llm-judge-cant-tell-recent-from-fictional`](../code/092-your-llm-judge-cant-tell-recent-from-fictional).

## What we did

The failure is worth stating plainly, because anyone running an LLM as a grader has it and mostly cannot see it. A model has no reliable sense of what day it is. Show it a candidate that mentions a release, a version or an event newer than its training data, and it cannot tell "real, recent, past my knowledge" from "made up". A kill-biased judge resolves that doubt the cheap way: it rejects the thing and calls the date hypothetical. Every one of our three jurors did exactly that, and each wrote a confident sentence about why a real month was science fiction.

The fix is embarrassingly small. We prepend a short grounding preamble to each juror's system prompt that does two things:

- States **today's real date**, injected at call time, so the model knows where "now" actually is.
- Bans one specific move: **"it postdates what I know" is never a valid reason to kill**. Anything dated on or before today is a real point in the past or present. Judge the substance against the criteria.

That is the whole change. No date-stripping regex to maintain, no scrubbing of the candidate, nothing that breaks when a date is phrased oddly. It rides on both stances the panel runs (the adversarial gate and the lenient scoring pass), and it is inert on anything that never mentions a date. The date is injected fresh each run, and the template behind it is fingerprinted so the daily value does not trip our prompt-drift alarm.

## Why it was worth doing

Same candidate, before and after. Before grounding: a unanimous kill at 0.98, and every kill shot was about the calendar, not the argument. After grounding: the panel split, confidence fell to 0.60, one juror flipped straight to pass at 0.95 on the merits, and another wrote out loud that the grounding rule meant it "must not kill on temporal grounds alone". The disagreement-map judge then recommended overriding the last kill. The artifact was gone and the real debate could start.

The lesson has nothing to do with our stack. If you point a language model at fresh input, news, a new library version, this week's release notes, current events, and ask it to judge or grade or review, it will quietly mark the recent and true as invented. You will read it as a quality signal. It is a knowledge-horizon signal wearing a quality signal's clothes. Grounding the judge in the current date is the cheapest correction we have found, and it is a prompt, not a project.

## What's still off

Grounding stops the judge rejecting something for being recent. It does not let the judge verify a claim it has never seen. A genuinely false "recent" fact still needs a real source or a tool check, and that is a separate job we are not pretending this solves. It removes a false negative, it does not add knowledge. Separately, one juror errored on this run for an unrelated reason, a token budget too small for a reasoning model to finish, which we are fixing on its own ticket and which had nothing to do with the date fix.
