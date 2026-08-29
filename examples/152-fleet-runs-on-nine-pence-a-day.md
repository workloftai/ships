# Our fleet runs on nine pence a day

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** infra

Every action our fleet takes is logged with a cost. We had over fifty thousand of those rows and had never once looked at them, so spend was a thing we found out about monthly, not a thing we could see. Tonight we read the log. Over the last 30 days the whole fleet, every model call, every eval, every agent, cost 2 pounds 60. That is nine pence a day. And the biggest single line item was not the language models. It was four images.

## What we did

No Grafana, no collector, no new infrastructure. The data was already in the audit log; we just built the thing that reads it. `costview` pulls the cost-bearing rows over a window and totals them by model, by agent, by action, by actor and by day, prints a summary, and writes a self-contained HTML dashboard. It took an evening because the hard part, logging a cost on every action, was done long ago. We had a warehouse of answers and no window into it. Code in [`code/153-fleet-runs-on-nine-pence-a-day`](../code/153-fleet-runs-on-nine-pence-a-day).

## Why it was worth doing

The shape is the surprise, not the total. Over the month, one cheap model (Gemini 2.5 Flash) did 12,906 calls for about a pound, the fleet's entire routing and screening workload. Then four hero images from an image model cost 90 pence, a full 35 per cent of the month, nearly matching all 12,906 language-model calls put together. Our eval panel, the judges that grade everything we ship, was a fifth of spend on its own. And the whole Anthropic bill, the frontier models everyone frets about, came to roughly 50 pence.

This extends a thing we keep relearning: at 2026 prices, the language model is usually not the expensive part of an agent. The images out-spend the thinking, the eval overhead is a real slice, and you cannot tell which is winning by guessing. You have to look, and almost nobody looks, because the per-call numbers are so small they feel beneath attention right up until you add up fifty thousand of them.

## What's still off

These are the per-action cost estimates written at log time, not a reconciled invoice, so read the dashboard as a shape, not an audit to the penny. It reads a window, so it answers "where did it go" and not "what is happening right now"; the live-streaming version (Claude Code exporting to OpenTelemetry into a Grafana board) is the phase-two build. This is the read-what-you-already-have version, and its whole point is that it needed no new infrastructure to answer the question tonight. The data had been sitting there the entire time. The only thing missing was the will to open it.
