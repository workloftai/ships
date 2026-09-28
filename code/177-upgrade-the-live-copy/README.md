# 177 · We upgraded the wrong copy of Claude Code

Write-up: https://workloft.ai/ships/upgraded-the-wrong-copy-2026-09-28.html

Our main agent runs Claude Code as a long-lived service with Telegram and a web chat
attached. Upgrading it to 2.1.283 (for the new `/doctor prompt-audit`) went wrong twice:

1. `claude update` upgraded a copy of Claude Code the service does not run. The box
   has three installs: a native one, an npm one inside `~/.local/node_modules` (the
   one the service launches) and a stale global one on 2.1.177. Only the native one
   moved.
2. The first attempt at the audit was a bare `claude -p` launched from inside the live
   agent. It picked up a dead cached login instead of the service's auth, and it loaded
   the same Telegram plugin, which most likely took over the bot's polling connection.
   The live agent went deaf on Telegram until it was restarted.

Two small scripts came out of it.

**`which-claude.sh`** (read-only): lists every install it can find with its version,
then every running process using one of them. If the process you care about points at a
different install from the one you just upgraded, you upgraded the wrong copy.

```text
== installs found
~/.local/node_modules/@anthropic-ai/claude-code/bin/claude.exe   2.1.283 (Claude Code)
~/.local/share/claude/versions/2.1.283                           2.1.283 (Claude Code)
/usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe   2.1.177 (Claude Code)

== running processes using one of those installs
1719009  ~/.local/node_modules/@anthropic-ai/claude-code/bin/claude.exe
         ~/.local/node_modules/.bin/claude --dangerously-skip-permissions --
```

**`headless-child.sh`**: runs a one-off `claude -p` next to a live agent without it
touching the agent's channels. It loads the same auth the live agent uses, forces the
channel plugins off for the child only, and gives it an empty MCP config.

```bash
CLAUDE_BIN=~/.local/node_modules/.bin/claude \
AUTH_ENV=/etc/claude/env \
PLUGINS_OFF=telegram@claude-plugins-official,web@your-channels \
./headless-child.sh "/doctor prompt-audit" > prompt-audit.md
```

Upgrading the npm copy is `cd ~/.local && npm install @anthropic-ai/claude-code@<version>`,
then restart the service. Check with `which-claude.sh` afterwards, not before.

Caveats: the plugin ids are ours, so swap in your own. The Telegram cause is our best
reading of the timing, not something we reproduced on purpose. Bash and Linux `/proc`
only.
