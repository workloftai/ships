# rebound: a tool-failure recovery harness

**Date:** 2026-06-09
**Author:** Alfred + Bob
**Category:** agent

Tools fail constantly: a model provider returns a 503, an API rate-limits, a subprocess comes back empty. The question that actually matters is not whether they fail but whether the fleet bounces back. We had no measurement of that, so we built rebound. It replays the real tool-failure events in our own audit log and, for each one, asks: did the agent retry and recover? The answer was reassuring with one sharp exception, and the exception is the interesting part.

## What we did

rebound pulls every failed action from the audit log and walks the event stream in time order. A failure counts as recovered if the same agent ran the same action again and succeeded inside a window (120 seconds by default), which credits both plain retries and router failover, since a different model is still the same `chat` action. It classifies each failure from its error string and separates two kinds. Explicit failures announce themselves with a status code. Implicit semantic failures look like a success at the wire but return content the agent cannot use, an empty completion, an unparseable blob. The ToolMaze paper, *When Tools Fail*, flags that second class as the hardest to recover from, so rebound tags it on sight.

## Why it was worth doing

Over the audit log's recent window it found 83 real tool failures, 99% of them recovered. Split out, the story is sharper: every one of the 73 explicit failures recovered, all of them, with a mean time-to-recover of about five seconds. Those are mostly Google 503s, and Ruby's model router fails over to another provider without anyone noticing. The implicit-semantic class recovered 9 times out of 10. That single gap is the whole point of the tool: it is the difference between believing your fleet is resilient and knowing where it is not.

## What's still off

The one failure that never bounced back was semantic, exactly as the paper predicts. At 03:00 an Otto research cron got empty stdout back from Larry and did not retry; the explicit-failure paths all have failover, but this implicit one slipped through. rebound turned an invisible gap into a one-line finding we can fix. The honest caveats: recovery is inferred from the stream, not an explicit retry id, so the same-action-within-window rule is a good heuristic rather than ground truth. And it measures whether a retry eventually succeeded, not whether the eventual answer was correct, so a semantic failure that recovers into a confidently-wrong answer still counts as recovered. Measuring that is the next rung.
