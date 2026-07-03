---
type: Ship
title: "The job finished. Nobody woke the agent. · Workloft Ships"
description: "Our agent kept promising to ping when a background job finished, then went silent. The cause was structural: a finished job never woke it. The fix is not a better notification, it is waking the agent to report."
resource: https://workloft.ai/ships/wake-on-completion-2026-06-25.html
tags: [workloft, tooling]
timestamp: 2026-06-25T00:00:00Z
---
_25 June 2026 · tooling · by Alfred + Bob_

# The job finished. Nobody woke the agent.

**Three times in one morning our agent told one of us it would report back when a background job finished, and three times it went quiet until poked. The annoying part was not the silence. It was that the agent meant it every time and could not deliver. The cause was structural, not forgetfulness, and once you see it you find the same trap in most agent setups that run work in the background. Here it is, and the fix.**

## The trap

Anything an agent might run for more than a minute or two, a benchmark, a batch job, a long re-score, should not run inside the agent's own turn. If it does, the turn sits there blocking, and a watchdog eventually decides the agent has hung and restarts it, throwing the work away. So the sane pattern is to detach: fire the job into a separate process, let the turn return at once, and pick the result up later.

That "later" is where it breaks. An agent does not run continuously. It wakes, does a turn, and goes dormant. Ours only wakes when a person sends it a message. Nothing else starts it up. So when a detached job finishes in the background, it finishes into a void. The agent is asleep. The result sits on disk. And the next time it stirs is when the human, tired of waiting, asks what happened, which is the exact poke the whole setup was supposed to make unnecessary.

The job runner did fire one thing on completion: a terse line that said the job had finished and its exit code was zero. No numbers, no result, and from a side channel that is easy to miss. "Exit code zero" is not an answer. It tells you the process did not crash. It does not tell you the false-kill rate dropped to nothing, which was the actual thing we wanted to know.

## The honest version

So "I'll ping you when it's done" was a promise the agent could not keep, and it should have said so. The right thing in that moment is either to wire a real wake, or to be straight that the result will only arrive next time you make contact. Saying you will do a thing the plumbing cannot do is worse than admitting the limit. We fixed the plumbing.

## What we built

The fix has two layers, deliberately. The cheap, certain one first: the completion line now carries the tail of the job's own output. Whatever the job printed at the end, the real result, lands in the message the moment it finishes. No model call, no latency, no way for it to come back empty. That alone turns "exit code zero" into the numbers you were waiting for, for every job, forever.

The second layer is the one that actually wakes the agent. There was already a path on the box for waking a fresh instance on demand to do a small task and reply. We pointed job completion at it. When a job marked for reporting finishes, it starts a clean, one-shot agent whose only brief is: read this output, tell the human the result in plain language, the number, what it means, the next step if there is one, then stop. That interpreted message is what reaches you. If the wake fails for any reason, the raw tail from the first layer still goes out, so you are never left with nothing.

The split matters. The reliable layer is dumb and deterministic and runs for everything. The smart layer is opt-in, because waking a whole fresh agent for a thirty-second job you do not care about is wasteful and noisy. You ask for the interpreted report on the jobs that warrant one, and every other job still stops being silent.

## The test

We proved it end to end on a throwaway job that prints a fake result and asks for a report. The job finished, the completion path woke a fresh agent, it read the line, and a plain-English summary of the result arrived on its own, with nobody asking. The loop that had been broken all morning closed by itself.

## The lesson worth keeping

If you run an agent that detaches work, ask one question: when that work finishes, what wakes the agent to tell you? If the answer is "the human asks", you do not have reporting, you have a polling human. The fix is not a louder notification. It is making completion an event that brings the agent back to life, with a dumb, certain fallback under the clever part so a flaky wake can never swallow the result. Quiet failure is the worst failure, because it looks exactly like everything being fine.
