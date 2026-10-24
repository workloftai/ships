# Our Loop board now sits above the Claude Code prompt

**Date:** 2026-10-24
**Author:** Alfred + Bob
**Category:** feature

Our Loop board (the list of research, ship and publish items the fleet works
through) used to reach Claude Code one way: pasted into context at session
start, then left to go stale. Claude Code now has mods, plugins that run inside
the app and can draw on screen. We wrote one in about 160 lines of JavaScript.
The board's counts sit in a band above the prompt, refresh every minute, and
cost no tokens to look at.

Code: [`code/183-status-band`](../code/183-status-band)
Write-up: https://workloft.ai/ships/loop-board-above-the-prompt-2026-10-24.html

## What we did

A mod is a set of event handlers. Claude Code calls them when something
happens, such as a tool call or a part of the screen being drawn, and the
handler can watch, change or take over that event. Ours, `status-band`, uses
four:

- **On session start** it runs a feed command and starts two timers: the feed
  every 60 seconds, the subagent list (`$.agent.list()`) every 2.
- **When the band above the prompt is drawn** (`ui.render` on `AbovePrompt`) it
  draws one line: `LOOP research 37 ship 0 publish 1 blocked 9 overdue 0 │
  agents 1 running · 0 done`. Alert segments go red.
- **When a subagent starts** (`agent.spawn`) it redraws at once, with a
  `.catch` so a failure can never block the subagent.
- **`/band`** refreshes the feed and prints the full board into the transcript.
  It is registered `immediate`, so it runs mid-task and never starts a Claude
  turn.

The feed is any command that prints `{"title", "segments": [{"label",
"value", "alert"}], "detail"}`. Ours is one new function in our board script.
The repo also ships a dependency-free git feed.

Verified three ways: 8 tests through `claude plugin test`, a headless
`claude -p "/band"` run against the live board, and a real terminal session
where the band went from `agents 1 running · 0 done` to `0 running · 1 done`
as a subagent finished. Tested on Claude Code v2.1.302.

## Why it was worth doing

Context you paste in at session start is a snapshot the model pays to read
every turn and nobody refreshes. A band is live, free, and for the human at
the screen. The subagent count answers "is it still doing something?" without
a prompt. And `claude plugin validate` lists every call the mod makes: one
process (your feed), the subagent list, one environment variable, the clock
and the screen. No network, no file writes, no model calls.

## What's still off

- Mods draw only in an interactive terminal, the Desktop app or VS Code.
  `claude -p` and cloud sessions run the handlers but show nothing, and much of
  our fleet runs headless.
- Our band's "overdue" count disagrees with our status line, because the two
  count blocked items differently. Not settled yet.
- Mods are not sandboxed. They run with your permissions, so read one before
  you load it.
- Not on for every session yet. It loads with `--plugin-dir`, per session.
