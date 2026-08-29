# costview — where an agent fleet's money actually goes

If every action your agents take is logged with a cost, you are sitting on the
answer to "where does the spend go" and probably never look, because each number
is too small to notice until you add up fifty thousand of them. This reads those
rows and shows you the shape.

No Grafana, no collector, no new infrastructure. It queries the cost-bearing rows
over a window, totals them by model, agent, action, actor and day, prints a
summary, and writes a self-contained HTML dashboard.

```bash
python3 costview.py --days 30 --out dashboard.html
```

## What we found on our own fleet

Over 30 days: total ~$2.60, nine pence a day, 13,557 billed actions.
- Gemini 2.5 Flash: 12,906 calls for ~$1.03. The workhorse, near-free per call.
- Four image generations: ~$0.90, 35% of the month, nearly matching all 12,906
  language-model calls combined.
- The eval panel (`poll_juror`): ~21% of spend on its own.
- The entire Anthropic bill: ~$0.50.

The lesson: at 2026 prices the language model is usually not the expensive part
of an agent. Images, eval overhead and harness cost compete for the top of the
bill, and you cannot tell which is winning without looking.

## Make it yours

It reads from a Supabase table (`workloft_audit_log`) via our audit logger's
creds. Swap `fetch_cost_rows()` for your own cost store (a table, a Postgres
query, a JSONL of billed events); everything downstream (`aggregate`,
`render_html`) is a plain dictionary of `{cost, n}` per bucket and is portable.

## Honest limits

These are the per-action cost estimates written at log time, not a reconciled
invoice, so read it as a shape not an audit. It reads a window, not a live
stream, so it answers "where did it go", not "what is happening now". The
live-streaming version (Claude Code to OpenTelemetry to Grafana) is the phase-two
build; this is the read-what-you-already-have version.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
