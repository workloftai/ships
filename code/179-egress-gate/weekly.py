#!/usr/bin/env python3
"""Weekly line to Alfred: what egress-gate saw, and every override typed to get
past a gate. The point is that a human sees the overrides, not only the agent
that typed them.

Usage: weekly.py [--days 7] [--dry]   (cron: Fridays 16:30 UTC; emails via a local notify.to_email helper)
"""
import collections
import json
import os
import sys
import time

HOME = os.path.expanduser("~")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HOME, "oversight-scorecard"))
sys.path.insert(0, os.path.join(HOME, "notify"))
import egress_gate as g  # noqa: E402

days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 7
cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))

checks = collections.Counter()
rules = collections.Counter()
flagged = []
egress_overrides = []
try:
    with open(g.LOG) as f:
        for ln in f:
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if e.get("ts", "") < cutoff:
                continue
            if e.get("event") == "check":
                checks[e["decision"]] += 1
                if e.get("rule") and e["rule"] != "tainted_clean":
                    rules[e["rule"]] += 1
                    flagged.append(e)
                elif e.get("rule") == "tainted_clean":
                    checks["tainted_clean"] += 1
            elif e.get("event") == "override":
                egress_overrides.append(e)
except OSError:
    pass

try:
    import scorecard
    _, gate_blocks, _, typed_overrides, _ = scorecard.scan_transcripts(scorecard.since_iso(days))
except Exception as exc:  # report the gap rather than going quiet
    gate_blocks, typed_overrides = None, f"unavailable ({exc.__class__.__name__})"

total = checks["allow"] + checks["would_block"] + checks["block"]
lines = [
    f"EGRESS + OVERRIDES · last {days} days",
    "",
    f"Outbound web calls checked: {total}",
    f"  allowed: {checks['allow']} (of which from a tainted session, nothing leaked: {checks['tainted_clean']})",
    f"  would block (monitor mode): {checks['would_block']}",
    f"  blocked: {checks['block']}",
]
for e in flagged[-10:]:
    lines.append(f"    {e['ts'][:16]} {e['rule']} {e['tool']} -> {e['host']} [{', '.join(e.get('labels', []))}]")
lines += ["", f"egress-ok overrides: {len(egress_overrides)}"]
for e in egress_overrides[-10:]:
    lines.append(f"    {e['ts'][:16]} {e['host']} for {e['minutes']} min")
if isinstance(typed_overrides, collections.Counter):
    lines.append(f"Overrides typed past other gates: {dict(typed_overrides) or 'none'}")
    lines.append(f"Gate blocks seen by the agent only: {sum(gate_blocks.values())} {dict(gate_blocks.most_common(5))}")
else:
    lines.append(f"Overrides typed past other gates: {typed_overrides}")
body = "\n".join(lines)

if "--dry" in sys.argv:
    print(body)
else:
    import notify
    n_typed = sum(typed_overrides.values()) if isinstance(typed_overrides, collections.Counter) else 0
    flagged_n = checks["would_block"] + checks["block"]
    notify.to_email(f"Egress + overrides: {total} checked, {flagged_n} flagged, "
                    f"{len(egress_overrides) + n_typed} overrides", body)
    print("sent")
