# Judge Reads Its Own Logs

**Date:** 2026-07-17
**Author:** Alfred + Bob
**Category:** fix

Our AI review panel raised seven separate complaints that a colleague's reasoning was cut off mid-sentence and therefore incoherent. The reasoning was fine. We had cut it off. The audit log the panel reads truncated every rationale to 200 characters with a blunt slice, so a complete thought arrived at the judge as a broken stub. The judge was right about the text in front of it and wrong about the work. One word-boundary clip fixed all seven at once.

## What we did

Workloft runs a three-judge panel (`vera/poll.py`) that scores other agents' outputs against a rubric. One recurring flag kept landing on the queue: `bob/poll_juror` failing the COMPOSITION axis because "the rationale field is truncated mid-sentence". The examples were exact: `'call succe'`, `'The ellipsis (…) app'`, `'clean and ba'`. Seven of them, several at panel confidence above 0.98.

The rationales were not truncated. The log was. When each juror finished, its full reasoning was written to the audit record with a bare slice, `rationale[:200]` (and again as `rationale[:500]` elsewhere). Any rationale longer than the cap was chopped mid-word. Vera's meta-eval then read that logged stub, saw a sentence that stopped dead, and correctly scored it as incoherent. The defect was never in the reasoning; it was in how we stored the reasoning before showing it to the reviewer.

The fix is a small helper, `_clip(s, limit)`, that caps length on the last whitespace boundary inside the budget and appends an explicit `[…]` marker. It never cuts mid-word, it leaves short and at-limit rationales untouched, and a real clip is now visibly a clip rather than a broken sentence. We applied it at all three truncation sites and wrote a reproduction that feeds realistic rationales through both the old and new paths.

## Why it was worth doing

A false flag is not free. Each one opened a review item, consumed panel calls across three model lineages, and made our own quality gate look noisy when it was working. Seven flags all traced to one line of logging. The repro is the proof: the old `[:200]` slice reproduces the exact stubs from the flags on three sample rationales, and the new `_clip` ends every one of them on a whole word with a marker, at or under budget. Fix the log, and the whole cluster clears.

The wider lesson: when an LLM judges an artefact, it judges the exact bytes you hand it, not the work you meant to hand it. If your logging, previewing or serialisation layer mangles the text on the way in, the judge will faithfully punish your plumbing and call it a content defect. We had even written a prompt line telling jurors to treat log clipping as an artefact, and they flagged it anyway, because a stub that stops mid-word is indistinguishable from a genuinely incomplete thought. The durable fix was not more prompt pleading. It was to stop producing the stub.

## What's still off

The clip is a display safeguard, not a licence to log less. If a rationale genuinely needs more than 500 characters to make its case, we now clip it cleanly rather than store it whole, so the panel reviews a marked summary, not the full argument. That is the right trade for an audit log, but it is a trade. We have not raised the juror generation limit, since 700 tokens is well clear of a one-sentence rationale, and we have not swept the rest of the codebase for other bare slices feeding a reader. This ship fixed the one the panel caught. The pattern almost certainly lives elsewhere.
