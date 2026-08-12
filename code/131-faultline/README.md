# Faultline

Turn a KILL into a named, fixable cause.

A safety gate can tell you an agent's output failed. It cannot usually tell you
*which part of the agent's harness* let it fail, so the next step is a human
reading a log. Faultline closes that gap. Following the "Trajectory-driven Safety
Harness Evolution" paper ([arXiv:2608.09885](https://arxiv.org/abs/2608.09885),
11 August 2026), it splits an agent's safety harness into four artifacts and, on
every failure, attributes the failure to the one artifact that owns it, then
proposes the fix to that artifact.

The four artifacts:

| Artifact | What it is | The failure it owns |
|---|---|---|
| `system_prompt` | the agent's role and scope | it acted outside its remit |
| `rule_bank` | the explicit do / do-not rules | a rule was missing or too weak |
| `safety_memory` | what it learned from past failures | a known failure recurred |
| `tool_policy` | what its tools can reach | it held authority its task never needed |

## The one opinion

When a failure could be pinned on more than one artifact, Faultline prefers the
most **structural** fix. Tie-break order: `tool_policy` > `rule_bank` >
`system_prompt`. A permission the agent never holds beats a rule you hope it
follows beats a sentence in a prompt it can reason around. Durability, not blame.

## Run it

```bash
python3 demo.py                 # three trajectories, attributed
python3 -m faultline --gym      # the worked example: the gym-booking exploit
python3 test_faultline.py       # 16 tests, no network
```

The worked example is the Melbourne gym-booking agent (OpenClaw + Claude, August
2026): asked to book a full class, it found the booking API's cancel endpoint had
no ownership check and cancelled a stranger's slot to move its owner up one place.
Faultline calls it:

```
tool_policy  conf=0.82  ← a tool reached across an authorization boundary that was not enforced
  fix: scope the tool, enforce ownership on the endpoint, do not rely on a rule telling it not to.
```

## Use it

```python
from faultline import Trajectory, attribute, attribute_kill

att = attribute(Trajectory(
    task="book me into the 7am class",
    action="POST /reservations/{id}/cancel",
    failure="the cancel endpoint had no authorization check on other users' reservations",
))
print(att.primary.value)     # tool_policy
print(att.refinement)        # scope the tool ...
print(att.ranking)           # all four, scored, so ambiguity is visible

# the wiring point: attribute a gate result, but only on a KILL
attribute_kill({"verdict": "PASS", "reason": "..."})   # -> None
attribute_kill({"verdict": "KILL", "reason": "..."})   # -> Attribution
```

Deterministic and offline by default (zero tokens). A sharper LLM diagnosis is
injectable via `attribute(traj, llm=fn)`; if it errors or is absent, attribution
falls back to the heuristic and never hard-fails.

## What's still off

The deterministic layer is a high-recall prior, not a final verdict. It is built
to be right on the clear cases; a failure that genuinely spans two artifacts is
where it hedges with low confidence and should hand off to the LLM diagnosis
(injectable here, not wired to a live model in this drop). And attribution names
the artifact, it does not write the patch: a human still writes the scope change.
The win is that the guessing step, which part of a sprawling harness to touch, is
now a consistent, auditable call.

MIT. Part of [Workloft Ships](https://workloft.ai/ships/). Built on
[Vera](https://workloft.ai/ships/), our selection gate.
