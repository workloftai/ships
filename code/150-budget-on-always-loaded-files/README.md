# claude_md_budget — a gauge for the files loaded into every session

`CLAUDE.md`, `AGENTS.md` and your agent's memory index get loaded into context on
every single turn. They only ever grow, one small edit at a time, and nothing
tells you when the accumulation has become a tax you pay on every message. This
tells you.

It is a Claude Code **PostToolUse hook** with zero dependencies. After a write or
edit to a watched file, it estimates the token size, compares it to a budget, and
if it is over it prints a short warning naming the largest sections to move out.
It never blocks the edit and never moves anything. A gauge, not a gate.

## Use it as a hook

Add to `.claude/settings.json` under `PostToolUse`:

```json
{
  "matcher": "Write|Edit|MultiEdit",
  "hooks": [{ "type": "command", "command": "/abs/path/claude_md_budget.py", "timeout": 5 }]
}
```

Edit the `WATCHED` set (basenames) and `BUDGET_TOKENS` (or the
`CLAUDE_MD_BUDGET_TOKENS` env var) at the top of the file.

## Use it as a CLI

```bash
python3 claude_md_budget.py CLAUDE.md            # report: size vs budget + biggest sections
python3 claude_md_budget.py CLAUDE.md --apply     # extract the biggest section into .claude/rules/
```

`--apply` is deliberately timid: it moves one section, writes a `.bak` first, and
leaves a one-line pointer where the section was. It will not restructure the file
for you, because deciding what an always-loaded file should say is a judgement,
not a byte count.

## What it caught first

We ran it against our own setup and it immediately flagged our memory root index,
19 tokens over a 1500 budget, and fingered the exact section that had drifted: a
growing pile of loose pointers our own filing rules said should have been folded
into topic files. We knew the rule. We were quietly breaking it.

## Honest limits

The token count is `len / 4`, an estimate, not a real tokeniser (close enough for
a gauge, wrong for an invoice). It matches by filename, so the watch list is
configured, not discovered. And a budget is a heuristic: sometimes the context
earns its tokens and you should raise the number, not gut the file.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
