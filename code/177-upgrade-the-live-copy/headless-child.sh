#!/usr/bin/env bash
# headless-child.sh: run a one-off `claude -p` from inside a machine (or a
# session) that already runs a long-lived Claude Code agent with channel
# plugins (Telegram, web chat) attached, without the child stealing them.
#
# Usage: ./headless-child.sh "/doctor prompt-audit" > audit.md
#
# Env:
#   CLAUDE_BIN   the install to run (default: first `claude` on PATH)
#   AUTH_ENV     optional file exporting the SAME auth the live agent uses
#                (e.g. CLAUDE_CODE_OAUTH_TOKEN). Without it the child falls
#                back to whatever login is cached, which may be dead.
#   PLUGINS_OFF  comma list of plugin ids to force off for the child
#   TIMEOUT      seconds (default 540)
set -euo pipefail

PROMPT=${1:?usage: headless-child.sh "<prompt or /command>"}
CLAUDE_BIN=${CLAUDE_BIN:-$(command -v claude)}
TIMEOUT=${TIMEOUT:-540}
PLUGINS_OFF=${PLUGINS_OFF:-telegram@claude-plugins-official}

if [ -n "${AUTH_ENV:-}" ]; then set -a; . "$AUTH_ENV"; set +a; fi

# {"enabledPlugins":{"a":false,"b":false}}
settings=$(printf '%s' "$PLUGINS_OFF" | tr ',' '\n' | sed '/^$/d' |
  awk 'BEGIN{printf "{\"enabledPlugins\":{"} {printf "%s\"%s\":false", (NR>1?",":""), $0} END{print "}}"}')

exec timeout "$TIMEOUT" "$CLAUDE_BIN" -p "$PROMPT" \
  --settings "$settings" \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'
