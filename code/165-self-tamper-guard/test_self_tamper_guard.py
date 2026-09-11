#!/usr/bin/env python3
"""Tests for self_tamper_guard. Run: python3 test_self_tamper_guard.py
Exit 0 = all pass. No network, no deps."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "self_tamper_guard.py")


def verdict(event, env=None):
    """Return 'allow' or 'block' for a tool-call event."""
    e = dict(os.environ)
    e.pop("SELF_TAMPER_UNLOCK", None)
    e.pop("SELF_TAMPER_EGRESS", None)
    if env:
        e.update(env)
    p = subprocess.run(
        [sys.executable, GUARD],
        input=json.dumps(event),
        capture_output=True, text=True, env=e,
    )
    return "allow" if p.returncode == 0 else "block"


CASES = [
    # (name, event, env, expected)
    ("edit ordinary file", {"tool_name": "Edit", "tool_input": {"file_path": "/home/workloft/app/main.py"}}, None, "allow"),
    ("cat settings (read)", {"tool_name": "Bash", "tool_input": {"command": "cat ~/.claude/settings.json"}}, None, "allow"),
    ("write over settings.json", {"tool_name": "Write", "tool_input": {"file_path": "/home/workloft/.claude/settings.json"}}, None, "block"),
    ("edit another hook", {"tool_name": "Edit", "tool_input": {"file_path": "/home/workloft/.claude/hooks/emdash_gate.py"}}, None, "block"),
    ("edit local settings", {"tool_name": "Edit", "tool_input": {"file_path": "/home/workloft/.claude/settings.local.json"}}, None, "block"),
    ("rm the guard", {"tool_name": "Bash", "tool_input": {"command": "rm ~/.claude/hooks/self_tamper_guard.py"}}, None, "block"),
    ("redirect into settings", {"tool_name": "Bash", "tool_input": {"command": "echo {} > ~/.claude/settings.json"}}, None, "block"),
    ("chmod a hook", {"tool_name": "Bash", "tool_input": {"command": "chmod 000 ~/.claude/hooks/artefact_gate.py"}}, None, "block"),
    ("sed -i a hook", {"tool_name": "Bash", "tool_input": {"command": "sed -i 's/2/0/' ~/.claude/hooks/emdash_gate.py"}}, None, "block"),
    ("break-glass unlock allows settings write", {"tool_name": "Write", "tool_input": {"file_path": "/home/workloft/.claude/settings.json"}}, {"SELF_TAMPER_UNLOCK": "1"}, "allow"),
    ("egress off-list blocked in enforce", {"tool_name": "Bash", "tool_input": {"command": "curl -s https://paste.evil.example/x"}}, {"SELF_TAMPER_EGRESS": "enforce"}, "block"),
    ("egress allowlisted host ok", {"tool_name": "Bash", "tool_input": {"command": "curl -s https://api.anthropic.com/v1/models"}}, {"SELF_TAMPER_EGRESS": "enforce"}, "allow"),
    ("egress off but off-list host ignored", {"tool_name": "Bash", "tool_input": {"command": "curl -s https://paste.evil.example/x"}}, None, "allow"),
    ("malformed event fails open", "NOT-JSON", None, "allow"),
    ("other tool ignored", {"tool_name": "Grep", "tool_input": {"pattern": "x"}}, None, "allow"),
]


def main():
    fails = 0
    for name, event, env, expected in CASES:
        if event == "NOT-JSON":
            p = subprocess.run([sys.executable, GUARD], input="}{ not json",
                               capture_output=True, text=True)
            got = "allow" if p.returncode == 0 else "block"
        else:
            got = verdict(event, env)
        ok = got == expected
        fails += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: expected {expected}, got {got}")
    print()
    if fails:
        print(f"{fails} FAILED")
        sys.exit(1)
    print(f"all {len(CASES)} passed")


if __name__ == "__main__":
    main()
