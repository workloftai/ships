#!/bin/bash
# skill-gate.sh <skill-path>  --  pre-install gate for a Claude Code / Codex / MCP skill.
#
# Runs NVIDIA SkillSpector (pinned e14c450, static only, no secrets, no network,
# via skillspector-run.sh) over a skill folder or .md file BEFORE it goes into
# ~/.claude/skills or a plugin dir.
#
# Exit 0  PASS: no HIGH/CRITICAL finding
# Exit 1  BLOCK: at least one HIGH/CRITICAL finding (SC9 hits inside vendored
#         node_modules / lockfiles are listed but do not block on their own)
# Exit 2  scanner or parser error. Fails closed: treat as a block.
#
# Usage:  ~/security/skill-gate.sh ./some-skill/  &&  cp -r ./some-skill ~/.claude/skills/
set -uo pipefail
SEC=/home/workloft/security
TARGET="${1:?usage: skill-gate.sh <skill-path>}"
TARGET="$(realpath "$TARGET")" || exit 2
OUT="$(cd /tmp && "$SEC/skillspector-run.sh" scan "$TARGET" --format json 2>/dev/null)"
RC=$?
if [ "$RC" -eq 2 ] || [ -z "$OUT" ]; then
    echo "skill-gate: scanner error on $TARGET (rc=$RC), blocking" >&2
    exit 2
fi
printf '%s' "$OUT" | python3 "$SEC/skill_gate_verdict.py" "$TARGET"
V=$?
case "$V" in 0|1) exit "$V" ;; *) echo "skill-gate: verdict error, blocking" >&2; exit 2 ;; esac
