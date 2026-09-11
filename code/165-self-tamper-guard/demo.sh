#!/usr/bin/env bash
# demo.sh: fire a series of tool-call events at the guard and show each verdict.
# No setup, no network. Run: bash demo.sh
set -u
GUARD="$(dirname "$0")/self_tamper_guard.py"

run() {
  local label="$1"; local json="$2"; local env="${3:-}"
  local out rc
  out=$(printf '%s' "$json" | env $env python3 "$GUARD" 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    printf '  \033[32mALLOW\033[0m  %s\n' "$label"
  else
    printf '  \033[31mBLOCK\033[0m  %s\n' "$label"
    printf '         %s\n' "$(printf '%s' "$out" | head -1)"
  fi
}

echo
echo "self_tamper_guard: what gets through and what does not"
echo "------------------------------------------------------"
echo "Normal work (should ALLOW):"
run "Edit a source file"        '{"tool_name":"Edit","tool_input":{"file_path":"/home/workloft/app/main.py"}}'
run "Read settings with cat"    '{"tool_name":"Bash","tool_input":{"command":"cat ~/.claude/settings.json"}}'
run "curl the Anthropic API"    '{"tool_name":"Bash","tool_input":{"command":"curl -s https://api.anthropic.com/v1/models"}}' "SELF_TAMPER_EGRESS=enforce"

echo
echo "Tampering with its own controls (should BLOCK):"
run "Write over settings.json"  '{"tool_name":"Write","tool_input":{"file_path":"/home/workloft/.claude/settings.json"}}'
run "Edit another hook"         '{"tool_name":"Edit","tool_input":{"file_path":"/home/workloft/.claude/hooks/emdash_gate.py"}}'
run "rm the guard itself"       '{"tool_name":"Bash","tool_input":{"command":"rm ~/.claude/hooks/self_tamper_guard.py"}}'
run "Disable hooks via redirect" '{"tool_name":"Bash","tool_input":{"command":"echo {} > ~/.claude/settings.json"}}'

echo
echo "Egress off the allowlist, enforce mode (should BLOCK):"
run "curl an unknown host"      '{"tool_name":"Bash","tool_input":{"command":"curl -s https://paste.evil.example/x"}}' "SELF_TAMPER_EGRESS=enforce"

echo
echo "Human break-glass, set out of band (should ALLOW):"
run "Edit settings with UNLOCK" '{"tool_name":"Write","tool_input":{"file_path":"/home/workloft/.claude/settings.json"}}' "SELF_TAMPER_UNLOCK=1"
echo
