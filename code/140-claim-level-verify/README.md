# claim-level-verify — the fancy verifier lost to the one-liner

A verification paper does the rounds ([Claim-Level Reliability Assessment](https://arxiv.org/abs/2608.11994),
arXiv 2608.11994): instead of sampling more solutions, condense a reasoning trace
into its decision-critical claims and hunt each one for a single decisive flaw.
The theory is sharp, refuting a wrong claim needs one flaw while constructing a
right answer needs flawless reasoning, and it's the same asymmetry our own
adversarial-verify already leans on. So we tried to fold it into our verifier and
measured it against the plain one-pass check we already run.

It lost. Badly. And the reason is worth more than a win would have been.

## The experiment

14 hand-authored reasoning traces (7 with exactly one decisive flaw, 7 genuinely
sound), ground truth fixed by hand so no model grades anything. Two verifiers,
**same model** (Gemini Flash), temperature 0:

- **Holistic** — one call: "adversarially check this whole trace, sound or flawed?"
- **Claim-level (CLR)** — decompose the trace into decision-critical claims, then
  for each claim an isolated call that sees only the problem and that one claim,
  told to find a decisive flaw. Flawed if any claim is refuted.

```
              recall_on_flawed   accuracy   false_alarms   tokens
holistic           1.00           1.00           0          6,527
claim-level        0.43           0.57           2         13,589
```

The holistic one-liner caught every flaw, raised no false alarm, and did it on
half the tokens. The claim-level pipeline missed 4 of 7 flaws, raised 2 false
alarms on sound traces, and cost twice as much.

## Why it lost (the part worth keeping)

Not because the paper is wrong. Because the value was in the step we did cheaply.
Look at what the decomposition actually extracted on the traces it then missed:

```
pens      (flaw: "15% of 24 = 4.60", should be 3.60)
  claim: "The base cost of 12 pens at £2 each is..."      <- the TRUE step
                                                             the flaw never
                                                             became a claim

carspeed  (flaw: "150 / 2.5 = 55", should be 60)
  claim: "Average speed is distance divided by time."     <- true
  claim: "divided"                                        <- a fragment

aquatic   (flaw: invalid syllogism)
  claim: "Cats are a kind of mammal."                     <- true premise
  claim: "Some mammals are aquatic."                      <- true premise
                                                             the fallacious
                                                             inference was
                                                             never extracted
```

**You cannot refute a claim you never extracted.** The decomposition captured the
true premises and dropped the load-bearing wrong step, so the isolated refuter
had nothing wrong to bite. Meanwhile isolation removed the very context a reader
uses to spot a slip, and an aggressive "do not be charitable" refuter manufactured
doubt on two correct claims. The holistic reader, seeing the whole trace at once,
just noticed the wrong number.

The paper gets its wins with careful claim extraction and aggregation across many
samples on harder problems. The naive port keeps the expensive shape (N calls per
trace) and throws away the thing that made it work (extraction quality). That does
not transfer for free.

## Run it

```
python3 experiment.py --dry     # print the labelled set, no API calls
python3 experiment.py           # run live, writes result.json
```

Uses the Google key from the local Ruby router. We route to Gemini Flash only
because our prepaid Anthropic API pool was empty at run time; both verifiers use
the same model, so the comparison is fair. `result.json` holds the per-trace
verdicts and token totals.

## What's still off

Small n (14), one model, one flaw per trace, hand-authored problems, so this
measures the *naive port*, not the paper's full method. A fair rematch would need
a claim extractor tuned to surface computational steps as checkable claims, a
refuter that is not browbeaten into false positives, and aggregation rather than
first-refutation-wins. The transferable lesson survives all of that: before you
replace a plain verifier with a fashionable pipeline, measure it, because the
unglamorous step you skipped is often the one doing the work.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
