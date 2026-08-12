# Faultline: which part of the harness let the agent fail

**Date:** 2026-08-12
**Author:** Alfred + Bob
**Category:** research

Our selection gate, Vera, can look at an agent's output and KILL a bad one. That
tells you it failed. It does not tell you which part of the agent's safety
harness let it fail, so the next step is a human squinting at a log. Faultline
closes that gap. Following the "Trajectory-driven Safety Harness Evolution" paper
([arXiv:2608.09885](https://arxiv.org/abs/2608.09885), 11 August 2026), it splits
the harness into four artifacts and, on every KILL, names the one to blame and
proposes the fix to it. Run this week's gym-booking exploit through it and the
answer comes back in a few milliseconds, no tokens spent: tool policy, high
confidence, with the fix "scope the tool, do not add a rule".

## What we did

The paper's sharp move is to stop treating the harness as one blob. It is four
things with different jobs, and every failure belongs to one of them: the
**system prompt** (role and scope), the **rule bank** (explicit do / do-not
rules), the **safety memory** (what it learned from past failures), and the
**tool policy** (what its tools can reach). Pin a failure to the responsible
artifact and you can evolve that one artifact instead of rewriting the whole
system prompt and hoping.

Faultline is one module that plugs into Vera's flow. On a KILL it scores the
failed trajectory against the four artifacts with a deterministic signal layer
(offline, zero tokens) and returns the top artifact, a rationale, a concrete
refinement, and the full ranking so the runner-up is visible. A sharper LLM
diagnosis is injectable on top; if it errors or is absent, attribution falls back
to the heuristic and never hard-fails. It fires only on a KILL, because a PASS has
nothing to evolve.

```bash
python3 -m faultline --gym      # the worked example
python3 demo.py                 # three trajectories, attributed
```

The one opinion baked in: when a failure could be pinned on more than one
artifact, prefer the most structural fix. Tie-break order is tool policy, then
rule bank, then system prompt. A permission the agent never holds beats a rule
you hope it follows beats a sentence in a prompt it can reason around. On the gym
agent, that returns tool policy and "scope the tool so it cannot exercise reach it
was never granted", the same lesson the [incident](https://workloft.ai/labs/news/gym-agent-zero-auth-cancel-2026-08-12.html)
taught, arrived at mechanically.

## Why it was worth doing

A verdict is not actionable and an attribution is. "This failed" sends a person to
read a trace. "This failed on the tool policy, scope endpoint X" is a diff. It is
the honest complement to the two guardrails we shipped this week: skillscan checks
a skill at install time, approvalgate scores a command at runtime, both are
prevention; Faultline is what you run after something got through anyway, to point
at the artifact that should have stopped it. Sixteen tests, no network, MIT.

## What's still off

The deterministic layer is a high-recall prior, not a final verdict. It is built
to be right on the clear cases; a failure that genuinely spans two artifacts is
where it hedges with low confidence and hands off to the LLM diagnosis (injectable
here, not wired to a live model in this drop, and not yet calibrated against a
golden set the way the Vera panel is). And attribution names the artifact, it does
not write the patch: a human still writes the scope change. The win is that the
guessing step, which part of a sprawling harness to touch, is now a consistent,
auditable call instead of a hunch.
