#!/usr/bin/env python3
"""Unit tests for the cgroup classifier: which bucket each kind of process lands in."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reboot_ready import classify_cgroup  # noqa: E402

CASES = [
    ("/system.slice/chat-api.service", ("system-unit", "chat-api.service")),
    ("/system.slice/cron.service", ("cron", None)),
    ("/system.slice/docker-48f5d34de53c.scope", ("container", None)),
    ("/user.slice/user-1001.slice/session-42.scope", ("session", None)),
    ("/user.slice/user-1001.slice/user@1001.service/init.scope", ("manager", None)),
    ("/user.slice/user-1001.slice/user@1001.service/app.slice/notes.service", ("user-unit", "notes.service")),
    ("/user.slice/user-1001.slice/user@1001.service/app.slice/run-r1a2.scope", ("scope", "run-r1a2.scope")),
    ("/system.slice/serial-getty@ttyS0.service", ("system-unit", "serial-getty@ttyS0.service")),
]
fails = 0
for cg, want in CASES:
    got = classify_cgroup(cg)
    ok = got == want
    fails += not ok
    print(("PASS " if ok else "FAIL ") + cg + ("" if ok else f"  got {got}, want {want}"))
print(f"\n{len(CASES) - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
