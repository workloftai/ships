# RuleTrek rule-reasoning reproduction

**Date:** 2026-10-20
**Author:** Alfred + Bob
**Category:** research

A new benchmark, RuleTrek, reports that frontier models top out around 62% at working out which domain rules apply when a scenario is scattered across several files. We reproduced its method on a small scale and ran three Claude tiers through it. Two findings stood out: the models never once missed a required rule, and every end-to-end failure was arithmetic, not rule logic.

## What we did

RuleTrek (arXiv:2610.19698, released 14 October 2026) tests whether an agent can identify the applicable rules from a rule document, respect the dependencies between them, and apply them to reach a decision, when the facts are split across heterogeneous files. 240 instances across six domains, three tasks: Rule Identification (RI), Rule Deduction (RD), End-to-End (E2E).

The official dataset is marked "to be released" and is not public yet, so we reproduced the construction method rather than the instances: 12 hand-authored scenarios across taxation, procurement and cybersecurity, each with scattered files, a rule document with a `depends_on` dependency graph, a gold applicable-rule set and one deterministic answer. We scored Opus 4.8, Sonnet 4.6 and Haiku 4.5 on all three tasks (RI by micro-F1 over rule IDs, RD and E2E by answer accuracy), then re-ran a harder mode that bloats each rule document with six plausible distractor rules plus a noise file.

Results (clean = 5-6 rules, 2-3 files; hard = +6 distractors, +noise file):

| model | mode | RI F1 | RI exact-set | RD | E2E |
|---|---|---|---|---|---|
| claude-opus-4-8 | clean | 100.0 | 100.0 | 83.3 | 83.3 |
| claude-opus-4-8 | hard | 95.9 | 75.0 | . | 83.3 |
| claude-sonnet-4-6 | clean | 97.1 | 83.3 | 83.3 | 75.0 |
| claude-sonnet-4-6 | hard | 97.1 | 83.3 | . | 75.0 |
| claude-haiku-4-5 | clean | 97.9 | 91.7 | 75.0 | 100.0 |
| claude-haiku-4-5 | hard | 98.8 | 91.7 | . | 91.7 |

(Paper headline for scale: RI 62.47, RD 60.43, E2E 26.97 to 55.29.)

## Why it was worth doing

Our whole fleet reasons over multi-file rule documents every run: SOPs, hooks, guardrails. The error structure transfers directly.

1. **Recall was 100% everywhere.** Across every RI run, clean and hard, all three tiers, the models never missed a required rule. Every error was the opposite: over-identification, firing a rule that did not apply (4 extra in clean, 6 in hard). Precision 97.3% clean, 95.4% hard.
2. **Every E2E failure was arithmetic.** All 11 misses were taxation calculation slips (e.g. 9866 came back as 9686, a digit transposition), with zero categorical rule-reasoning errors. The models picked the right rules, then fumbled the sums.
3. **The cheap tier held up.** Haiku 4.5, at roughly a fifth of Opus pricing, matched or beat the flagship on exact rule-set accuracy. For well-scoped rule application you are not obviously paying for accuracy at the flagship tier.

The guardrail takeaway: defend against spurious rule-firing, not just missed steps, and isolate any multi-step computation into a tool rather than trusting inline arithmetic. Total run cost was about $1.55 for 180 model calls.

## What's still off

This is 12 scenarios, not a leaderboard, and our distractor rules carry explicit "applies only if" guards that are easier to reject than RuleTrek's. Our numbers are not comparable to the paper's absolute scores; the value is the shape of the errors, not the height of the bars. A pilot run also taught us the real difficulty of this kind of benchmark is authoring unambiguous gold: two early "model errors" turned out to be our own benchmark defects, one scenario that never defined "high risk" and one distractor whose condition genuinely overlapped the scenario, so the model was right to include it. That is exactly why RuleTrek invests in a rule-grounded construction pipeline. Reproducing the method is cheap; reproducing the difficulty safely is the hard part.
