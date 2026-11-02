#!/bin/bash
# Run SkillSpector (pinned NVIDIA/SkillSpector @ e14c450) sandboxed:
#  - env -i: no secrets, no API keys, minimal PATH/HOME
#  - unshare -rn: empty network namespace, so no outbound calls at all
#    (OSV.dev lookups fall back to the built-in offline list)
#  - always --no-llm (static analysis only)
# Usage: skillspector-run.sh scan <path> [extra args]
VENV=/home/workloft/security/skillspector-venv
SCRATCH_HOME=/home/workloft/security/skillspector-home
mkdir -p "$SCRATCH_HOME"
exec env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$SCRATCH_HOME" LANG=C.UTF-8 \
  NO_COLOR=1 LANGSMITH_TRACING=false \
  unshare -rn "$VENV/bin/skillspector" "$1" --no-llm "${@:2}"
