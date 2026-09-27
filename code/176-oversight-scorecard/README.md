# 176 · We scored our fleet the way Anthropic scores its own

Write-up: https://workloft.ai/ships/our-oversight-numbers-2026-09-27.html

On 17 September 2026 Anthropic published three measures of agent oversight for its
~30,000 internal agents ([post](https://www.anthropic.com/institute/measuring-pace-of-ai-development)):
coverage, review latency and escalation rate, plus the share of research compute spent
on safety. It said any developer running agents could report the same. This does that
for a Claude Code fleet, from records you already have.

```bash
python3 scorecard.py                  # last 30 days
python3 scorecard.py --days 7 --json week.json
```

**Reads (read-only, stdlib only):**

- `~/.claude/projects/**/*.jsonl`: every tool call, and every one a PreToolUse hook refused.
- `~/.claude/settings.json`: which hooks see which tools before they run.
- Optional: an append-only audit table in Supabase (`SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `AUDIT_TABLE`) for agents and crons outside Claude Code.

**Reports:**

1. Coverage, split three ways: passed any pre-run hook; passed a hook that *judges*
   the action; got a safety screen. Plus the unjudged tools that reach the internet.
2. Escalation: blocks per gate, overrides typed to get past a gate, and whether any
   human sees them.
3. Spend on checking, or "NOT MEASURABLE" when the records can't support a number.

`GATE_KIND` at the top classifies each of our hooks (safety / content / process /
ordering). It is the one opinionated part: edit it for your own hooks.

Our result for the 30 days to 27 Sep 2026 is in `example-output-2026-09-27.txt`:
100% pass a hook, 64.3% pass one that judges them, 36.6% get a safety screen,
1 in 53 blocked (60% of those for em-dashes), 0 of 37,595 other fleet actions
checked before running.

## Honest limits

- Our gates are mostly house style, not safety, so our block rate is not comparable
  to Anthropic's in meaning, only in shape.
- The window is bounded by how long Claude Code keeps transcripts.
- Review latency to a human is reported as "none", because hook refusals go back
  to the agent, not to a person. That is a finding, not a gap in the script.
