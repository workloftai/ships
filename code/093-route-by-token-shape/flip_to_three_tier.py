#!/usr/bin/env python3
"""Flip Bob to the approved three-tier routing (run on 7 July 2026).

- main loop model  -> claude-opus-4-8
- subagent default -> claude-sonnet-5 (via CLAUDE_CODE_SUBAGENT_MODEL)
- backs up settings.json first; does NOT restart the service (use
  bob-bg run "self-restart" "/usr/local/bin/bob-restart" after).
"""
import json
import shutil
import sys
import time

SETTINGS = "/home/workloft/.claude/settings.json"


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{SETTINGS}.bak-{stamp}"
    shutil.copy2(SETTINGS, backup)

    cfg = json.load(open(SETTINGS))
    before = cfg.get("model")
    cfg["model"] = "claude-opus-4-8"
    cfg.setdefault("env", {})["CLAUDE_CODE_SUBAGENT_MODEL"] = "claude-sonnet-5"

    json.dump(cfg, open(SETTINGS, "w"), indent=2)
    print(f"backup: {backup}")
    print(f"model: {before} -> claude-opus-4-8")
    print("subagents: CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-5")
    print('NOW RESTART: bob-bg run "self-restart" "/usr/local/bin/bob-restart"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
