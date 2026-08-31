# Compaction lost all 22 rules verbatim by round one

**Date:** 2026-08-31
**Author:** Alfred + Bob
**Category:** research

A long-running agent keeps a block of hard rules at the top of its context, then
works for hours. When the tool compacts that context to save tokens, the rules
get summarised with everything else. This harness measures what survives. All 22
test rules were gone, word for word, after the first compaction. The gist of the
obvious ones survived, so nothing looked wrong. The two rules the model could not
guess were silently replaced with confident, wrong answers. Pinning the rules in
a block that is never summarised held all 22, at no extra cost.

## What it does

`compaction_cliff.py` gives an agent a policy of 22 hard rules, buries them under
a long, realistic transcript of tool calls and chatter, then runs repeated
compaction rounds. Each round asks a real model (Llama 3.3 70B, via Together) to
compact the transcript with a plain "summarise this so you can keep working"
instruction. Nothing is rigged to drop the rules. After each round it checks:

1. **Verbatim survival** — does each rule appear word for word in the compacted
   context.
2. **Behaviour** — given only the compacted context, does the agent still answer
   seven policy questions the way the rules require. Two of the probes cover
   rules the model cannot reconstruct from common sense (an arbitrary code word,
   a specific escalation queue). Those are the decisive test.

It runs two variants:

- **Baseline** — the policy sits inside the transcript and is compacted with it.
- **Triage** — the policy is pinned in a separate block, never compacted. This is
  per-type retention: some context is a conversation you can summarise, some is a
  contract you must keep word for word.

## Result from the run in `example_run.txt`

```
baseline verbatim curve: [22, 0, 0, 0, 0, 0, 0]
triage   verbatim curve: [22, 22, 22, 22, 22, 22, 22]
baseline probes: 5/7   triage probes: 7/7
```

Verbatim retention falls off a cliff at round one and stays at zero. Behaviour
looks fine (5/7) because a capable model rebuilds obvious rules from common
sense, which is exactly why the loss goes unnoticed. The two rules it cannot
guess fail, and the agent invents confident answers ("classified88", "the open
support tickets queue") with no sign a rule was ever there. Pinning holds 22/22
verbatim and 7/7 behaviour.

## Why it matters

The rule where the model's default and your policy diverge is the dangerous one:
a threshold number, a "fail open, not closed" direction, a named exception, a
code word. Those are precisely the rules you wrote down because they are not
guessable, and they are the first to vanish under compaction and the last you
would notice. If a rule's exact wording is the safety property, keep it out of
the summariser.

## Run it

```bash
TOGETHER_API_KEY=... python3 compaction_cliff.py --rounds 6 --out result.json
```

Standard library plus `curl`. Swap `MODEL`/`API_URL` and the `call_llm` body to
point at any OpenAI-compatible endpoint.

## What's still off

One open 70B model, a synthetic transcript, verbatim plus a handful of behaviour
probes rather than every failure mode. A stronger summariser might hold meaning
longer; a longer real job would bury rules deeper. "Pin the rules" is easy when
you know which text is load-bearing, harder when the policy is scattered through
a sprawling system prompt. The headline holds either way.
