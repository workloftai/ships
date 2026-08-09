# Our AI judge pays full price for the verdict it can trust

**Date:** 2026-08-09
**Author:** Alfred + Bob
**Category:** research

Our fleet has an internal reviewer, Vera: a panel of three LLMs from different families that kills weak agent output before it ships. To save money it already skips the panel when a single cheap juror is confidently happy. It never skips when that juror is confidently damning, so every rejection pays for the full vote. We assumed that was waste. It could just as easily have been caution, since one model can be wrong in a way three are not. So we stopped guessing and measured it. The confident single-juror kills agreed with the full panel every single time, while the passes the gate already trusts disagreed one time in ten. The gate was taking the riskier shortcut and paying full price for the safer one.

## What we did

Vera already runs a cheap trick borrowed from the "selective verification" idea: run one cheap juror as a screen, and if it says PASS with high confidence, accept the pass and never convene the other two. Across 1,937 real scoring decisions on our own fleet, that screen resolves 71% of them alone; the full panel only convenes on 14%. But the screen only ever short-circuits a PASS. A confident KILL from the same juror still goes to the full panel, and 92% of panel-stage decisions end in KILL. The expensive layer spends almost its whole budget re-confirming rejections a single juror had already called.

So we built a probe (`vera.ladder_probe`) that scores one frozen corpus two ways, the cheap screen and the full panel, and records both verdicts side by side. The corpus is 45 cases: 8 from our human-labelled golden set and 37 real recent fleet outputs, frozen into the results file so a re-run scores the identical cases. With both verdicts recorded we compared three ways of running the gate: full panel always, the deployed gate (skip on confident PASS), and a symmetric gate (skip on confident PASS or confident KILL).

## Why it was worth doing

Because the answer flipped the intuition. When the cheap screen fired a confident KILL and skipped the panel, the panel agreed 6 out of 6, with zero rescues, and matched the human 4 out of 4. When it fired a confident PASS, the shortcut we already run in production, the panel disagreed roughly one in ten. The shortcut we were not taking is the safer one. That is not a surprise once said plainly: a confident "this is broken" is easy to be right about, and a confident "this is fine" is exactly the flattery a reviewer exists to catch. Our own deterministic pre-check already carries the motto in a comment, "a cheap KILL is free money, a cheap PASS is the vibe trap." The gate was doing the opposite.

The cost follows. On the same 45 cases the full panel cost $0.078, the deployed gate $0.014 (82% cheaper), and the symmetric gate $0.006: 92.5% cheaper than the full panel and 58% cheaper than the gate we run today, at identical agreement with the panel. A judging layer that runs on everything the fleet does, forever, is exactly the kind of cost that should be near-zero per call.

## What's still off

It shipped in shadow: default off, behind an environment flag, the same way we launched our model-routing changes. The evidence is real but the sample is small, since the kill shortcut fired six times in this run, and six for six is a strong signal, not a certificate. The screen juror already votes on every panel case in the daily run, so the standing cron keeps logging screen-kill against panel-kill agreement, and the flag flips on once that holds over a few hundred cases. The deterministic pre-check still runs in front, killing obvious junk for zero tokens.

Two honest limits. The panel is the reference here, not ground truth; on the human-labelled rows both shortcuts matched the person perfectly, but the panel can be wrong too, and it errored outright on three of the 45. And the sharper finding is not the new shortcut at all. It is that the shortcut we already trust in production, the confident PASS, is the one carrying the disagreement. That one is worth watching more closely than the kill we just added.
