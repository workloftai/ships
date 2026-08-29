# We failed our own judge over a clipped log

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** fix

We grade our agents' work with a panel of language models, and a nightly meta-eval grades the panel. For weeks it kept failing one of our judges on composition, the axis for whether an output is complete and well-formed. The judge was fine. Our own logger had clipped its reasoning to 500 characters, cutting the last of a four-part rationale off mid-sentence, and the meta-eval was grading the stub, not the work. We failed our own judge for something we did to the record.

## What we did

Every juror vote is written to the audit log as a verdict, a confidence and a rationale. That rationale is where a good juror walks its four axes: selection, following, composition, reflection. A thorough one runs six to nine hundred characters. We were clipping it to five hundred, in two places, including the copy that lands in the audit record. So the fourth axis got sheared off, the logged rationale read as "names four axes, stops after three", and the composition check did exactly what it should with an output that trails off unfinished: it marked it down. The juror never had a problem. The logger did.

The fix is two lines of intent. Stop clipping the rationale on the vote we pass around, because the panel's own disagreement-map and minority-veto logic reason over that text, and clipping it was quietly starving them of evidence too. Then give the audit copy a budget that fits a complete rationale, sixteen hundred characters, cut on a word boundary with a visible marker so anything genuinely over-length reads as deliberately trimmed rather than broken. A regression test pins all three behaviours. Code and the portable clip helper are in [`code/151-failed-our-own-judge-over-a-clipped-log`](../code/151-failed-our-own-judge-over-a-clipped-log).

## Why it was worth doing

The lesson is bigger than one field. The record you log is the record your evaluation grades, and if you truncate it for tidiness you can fail your own system for work it did correctly. Ours was silent for 38 days: the juror kept scoring below bar, the board kept showing a flag, and every bit of it pointed at the model when the defect was in our plumbing. We had even been here before, twice, and fixed the same truncation pattern for the vote's title and made the clip word-safe, but the rationale's budget was still too small, so the bug survived in the one field that carried the actual reasoning. A false failure that names the wrong culprit is worse than a loud one, because you spend your attention in the wrong place.

## What's still off

Sixteen hundred characters fits our real rationales, but a pathologically long one still clips. It is now word-safe and visibly marked, and the scoring prompt already tells a juror to treat a marked clip as a logging artifact, not a defect, so the failure mode is contained rather than gone. The purist fix is to store the whole field and only trim for display, but audit-row size is a real constraint, so a generous word-safe cap is the honest line to draw. The durable takeaway is a question to ask of any observability you run: when it truncates, is anything downstream grading the truncation.
