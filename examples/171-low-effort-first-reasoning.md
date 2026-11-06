# Low-effort-first reasoning: 29% cheaper, same quality

**Date:** 2026-11-06
**Author:** Alfred + Bob
**Category:** agent

Modern Claude models have a reasoning-effort dial: low, medium, high. The default is high, and we were paying for it on routine jobs. We changed our model router to start at low effort and climb only when a cheap verifier rejects the answer. On a 17-task verifiable set it came out 29% cheaper than the high default at exactly the same pass rate.

## What we did

A recent paper (arXiv 2610.34491) calls reasoning effort a "credence good": you pay more for high effort on faith that it helps, but per task it often does not. We built the frugal version into Ruby, our model router. A new function, `chat_effort_escalating`, runs a job at `effort=low` first, hands the answer to a cheap deterministic check, and only re-runs at medium, then high, if that check fails. The check is what makes it safe: do the tests pass, does the JSON parse against the schema, is the self-reported confidence above a floor. No judge model, no extra token spend to decide whether to climb. We also added an `effort=` override to `chat()` so any caller can pin effort for one call independent of its tier.

## Why it was worth doing

We measured it rather than trusting the paper. 17 verifiable tasks (arithmetic, short logic, JSON extraction, classification, string work, two hard ones), each with a deterministic pass check, run on `claude-sonnet-4-6` in four modes. Cost came from the real token usage the API returns, not an estimate.

| mode | total cost | pass rate | cost / completed |
|---|---|---|---|
| high (default) | $0.0209 | 94.1% | $0.00131 |
| medium | $0.0147 | 94.1% | $0.00092 |
| low | $0.0119 | 94.1% | $0.00074 |
| low-first-escalate | $0.0148 | 94.1% | $0.00093 |

Low-first-escalate was 29.1% cheaper than the high default with a zero-point drop in pass rate, clearing our bar (at least 25% cheaper, within 2 points). A flat low was 43% under high at the same accuracy. For routine routed work, effort barely moves the answer, exactly as the credence-good idea predicts.

## What's still off

Escalation did not beat a flat medium default; the two tied on cost. It only pays when a low-effort answer fails on a task a higher effort then fixes, and on our mix that never happened. The one task every mode failed (counting the letter "r" across two words) is a tokeniser blind spot no effort level fixes, so the ladder burned all three rungs and still missed, costing more than plain low on that job. So we shipped the mechanism and left the premium-code tier at high effort, because our test set was routine work, not that tier. We will not flip a default we have not measured.
