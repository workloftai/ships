# cc-doctor

A zero-dependency auditor for the Claude Code settings that fail quietly.

Most people run Claude Code on the defaults, which is usually right. A few of
those defaults are not neutral: they delete your session history on a timer,
let an agent read your `.env` into context, or let it push to a remote on your
behalf. None of them ever error, so you find out late or never.

`cc-doctor.py` points at your config and tells you which of six such settings
are missing, why each matters, and the one-line fix. It reads your config and
never writes to it. Nothing is sent anywhere.

## Use

```bash
python3 cc-doctor.py                      # audit ~/.claude (+ ./.claude if present)
python3 cc-doctor.py --path /some/project # fold in that project's .claude
python3 cc-doctor.py --json               # machine-readable
python3 cc-doctor.py --quiet              # findings only
```

Exit codes: `0` no high-severity findings, `1` at least one high-severity
finding (drop it into CI as a gate), `2` bad usage or an unreadable file.

## The six checks

| setting | severity | fails how |
|---|---|---|
| `cleanupPeriodDays` | high | default 30 days silently deletes local transcripts |
| deny rule for `.env` | high | agent can read secrets into the context window |
| gate on `git push` | medium | agent can publish to a shared remote unprompted |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | low | background telemetry / error / update calls |
| `statusLine` | low | you cannot see context filling up, so cannot compact early |
| `includeCoAuthoredBy` | info | commits carry an AI co-authored-by trailer |

Every key is a real Claude Code setting, verified against the shipped binary.
Settings change between versions: if a check goes stale, update the rule, do not
trust the tool over the docs.

## Write-up

<https://workloft.ai/ships/settings-that-fail-quietly-2026-07-08.html>

MIT.
