# 179 · We checked 370 agent web calls for leaks

Write-up: https://workloft.ai/ships/checked-370-agent-web-calls-for-leaks-2026-10-01.html

A deterministic pre-run check on an agent's outbound web calls (Claude Code
`WebFetch`, `WebSearch`, Exa MCP). It borrows one idea from OpenAPPA
([repo](https://github.com/archestra-ai/OpenAPPA),
[paper](https://arxiv.org/abs/2607.24625)): track what the session has read, and
check every outbound call against that before it runs. No second model judges
anything. Same log, same policy, same answer.

It is not OpenAPPA. It is about 300 lines of Python wired in as two Claude Code hooks.

## The rules

1. **secret_in_payload** (always blocks). The URL or search query contains the value
   of a key from one of your `.env` files, or something shaped like a key
   (`sk-`, `ghp_`, `glpat-`, `AKIA`, JWT, Slack, Telegram bot token).
2. **tainted_flow** (logs in monitor mode, blocks in enforce mode). The session has
   read something from a taint source (`policy.toml`), the destination is not on the
   allow list, AND the URL or query repeats a fingerprint of what was read: a
   4-word phrase, an email address, or a long ID. Fingerprints are hashes; the text
   itself is never stored.
3. Everything else is allowed and logged. A tainted session that calls an unlisted
   host carrying none of that content is logged as `tainted_clean`.

`egress-ok <host> [minutes]` writes a time-boxed allow. Every override is logged,
and `weekly.py` emails the count to a human with the other gates' overrides.

## Wiring (`~/.claude/settings.json`)

```json
"PreToolUse":  [{"matcher": "WebFetch|WebSearch|mcp__exa__.*",
                 "hooks": [{"type": "command", "command": "/path/egress_gate.py check", "timeout": 5}]}],
"PostToolUse": [{"matcher": "Read|Grep|Glob|Bash",
                 "hooks": [{"type": "command", "command": "/path/egress_gate.py taint", "timeout": 5}]}]
```

## Result on our fleet

`replay.py` walks every past Claude Code session in order, feeds the reads to the
taint hook and the outbound calls to the check. 370 outbound calls across 33 sessions:

| | v1: label only | v2: content flow |
|---|---|---|
| calls from a tainted session | 177 (48%) | 177 |
| flagged | 177 | 1 |
| secret values in a URL or query | 0 | 0 |

`replay.py --canary` plants one leak per tainted session (a random 6-word run of
text that session actually read, sent to an unlisted host) plus every known secret
value. v2 caught 79 of 80 planted leaks and 22 of 22 secrets.

The one real flag was a false positive: a web search for a public model name and
price that also appeared in a private doc the session had read.

## Limits

- A bare two-word name ("Jane Doe") is under the 4-word phrase threshold and is not
  an email or ID, so it passes. `tests/test_egress_gate.py` pins this gap.
- Paraphrase beats it. This catches copy-paste leaks, not an agent that rewrites
  private content in its own words.
- It only sees the tools it is wired to. A `curl` in Bash goes round it; that is the
  shell screen's job.
- WebFetch's `prompt` is not checked, because it goes to the model that reads the
  page, not to the site.

## Run

```bash
python3 -c "import sys; sys.path.insert(0,'tests'); import test_egress_gate as t; [getattr(t,n)() for n in dir(t) if n.startswith('test_')]"
python3 replay.py --canary
python3 weekly.py --dry
```
