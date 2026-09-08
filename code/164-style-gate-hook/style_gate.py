#!/usr/bin/env python3
"""A Claude Code PreToolUse hook that HARD-enforces a house style rule.

The lesson this came from: a rule you write in a prompt (CLAUDE.md, a system
message, "please stop doing X") is probabilistic. The model follows it most of
the time and forgets it under load. If the rule is genuinely non-negotiable, put
it in a hook at the tool boundary, where enforcement is deterministic and the
model cannot talk its way past it.

This example blocks a banned-substring list (here: the em-dash and its HTML
entity forms) from reaching any human-facing surface:
  * chat/reply tools  -> the text the user will read
  * Write/Edit/MultiEdit -> generated copy files (.html/.md/.txt, build_*.py)

Two failure modes it was built to close, both real:
  1. The literal character is only half the problem. Generated HTML/PDF copy
     often carries entity forms (&mdash;, &#8212;, &#x2014;) that render as the
     banned glyph even though the source has no literal character. Ban both.
  2. A gate that only watches file writes misses the chat/reply tool entirely,
     which is where a lot of copy actually leaves. Cover the reply tools too.

Wire it in .claude/settings.json under hooks.PreToolUse with a matcher listing
your reply tool(s) and Write|Edit|MultiEdit, pointing at this script. Adjust
BANNED, the REPLY_TOOLS set, and _copy_file() for your own rule and stack.

Fails OPEN: any parse/internal error exits 0, so a broken gate never wedges work.
Exit 2 = block (stderr is shown to the model as the reason).
"""
import json
import os
import sys

# The rule. Replace with whatever your house style forbids.
BANNED = ("—", "―", "&mdash;", "&#8212;", "&#x2014;", "&#X2014;")

# Your chat/reply tool name(s). These carry a `text` field the user reads.
REPLY_TOOLS = {
    "mcp__plugin_telegram_telegram__reply",
    "mcp__plugin_telegram_telegram__edit_message",
    "mcp__plugin_web_web__reply",
}

# Internal-only paths where the rule does not apply (notes that document the rule
# must be free to contain the banned glyph). Tune to your layout.
EXEMPT_PATH_PARTS = ("/.claude/", "/memory/", "/hooks/")


def block(msg):
    sys.stderr.write(msg)
    sys.exit(2)


def is_copy_file(fp):
    if not fp:
        return False
    low = fp.lower()
    if any(p in low for p in EXEMPT_PATH_PARTS):
        return False
    if low.endswith((".html", ".md", ".txt")):
        return True
    base = os.path.basename(fp)
    return base.startswith("build_") and low.endswith(".py")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail open

    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}

    if tool in REPLY_TOOLS:
        content, surface = ti.get("text") or "", "message to user"
    elif tool in ("Write", "Edit", "MultiEdit"):
        fp = ti.get("file_path") or ""
        if not is_copy_file(fp):
            sys.exit(0)
        if tool == "Write":
            content = ti.get("content") or ""
        elif tool == "Edit":
            content = ti.get("new_string") or ""
        else:
            content = " ".join((e or {}).get("new_string", "") for e in ti.get("edits", []))
        surface = os.path.basename(fp)
    else:
        sys.exit(0)

    if any(b in content for b in BANNED):
        frags = [ln.strip() for ln in content.splitlines() if any(b in ln for b in BANNED)][:6]
        detail = "\n".join(f"  > {f}" for f in frags)
        block(
            f"BLOCKED by style gate ({surface}): outbound copy contains a banned form.\n"
            "This is a HARD rule enforced at the tool boundary, not a suggestion.\n"
            "Fix the copy (replace the banned form), do not retry unchanged.\n"
            f"Offending lines:\n{detail}\n"
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
