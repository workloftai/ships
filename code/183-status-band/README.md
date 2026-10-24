# status-band

A Claude Code mod that draws one line above the prompt:

```
LOOP  research 37  ship 0  publish 1  blocked 9  overdue 0  │  agents 1 running · 0 done
```

The left side comes from any command you choose that prints JSON. The right side is a live
count of this session's subagents, read from `$.agent.list()`. `/band` refreshes the feed and
prints its long-form `detail` into the transcript, without starting a Claude turn.

Tested on Claude Code v2.1.302 (mods need v2.1.287 or later).

## The feed contract

Your command prints one JSON object:

```json
{
  "title": "LOOP",
  "segments": [
    { "label": "research", "value": 37 },
    { "label": "blocked", "value": 9, "alert": true }
  ],
  "detail": "Markdown or plain text that /band prints"
}
```

`alert: true` draws that segment in red. A zero value is drawn dim. If a refresh fails, the last
good data stays on screen with a yellow `stale` marker, so a flaky feed never blanks the band.

## Run it

```bash
STATUS_BAND_CMD='["python3","/path/to/your_feed.py"]' claude --plugin-dir ./status-band
```

Or set the `command` (one argument per entry, no shell) and `interval_seconds` userConfig
values once installed. `STATUS_BAND_CMD` is the fallback when `command` is empty.

`examples/git_feed.py` is a feed with no dependencies: branch, uncommitted files, and commits
ahead of upstream. `examples/loop_board_band_json.py` is the shape of the feed we run.

Write-up: https://workloft.ai/ships/loop-board-above-the-prompt-2026-10-24.html

## Test it

```bash
claude plugin validate .
claude plugin test
```

8 tests: feed parsing, subagent bucketing, config fallback, drawing, the stale path, `/band`,
and the no-command case.

## What it can reach

`claude plugin validate` lists every call: `$.process.run` (your feed command only),
`$.agent.list`, `$.env.get` (`STATUS_BAND_CMD` only), `$.clock`, `$.command.register`, and
`$.ui`. No network, no file writes, no model calls.

MIT. Workloft, https://workloft.ai
