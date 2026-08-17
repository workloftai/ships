#!/usr/bin/env python3
"""
probe.py — which native Claude Code multi-agent primitives do you actually have,
and what bespoke "fleet plumbing" does each one let you retire?

The premise: a lot of what people hand-roll to make agents coordinate is now
built into the harness. But not all of it, and the two are easy to conflate.
This probe reads your installed Claude Code version and its changelog, detects
which native primitives are present, and maps each to the category of bespoke
plumbing it does (or does NOT) replace.

Three buckets, because "agent plumbing" is really three different jobs:
  1. INGRESS      — getting an external event (a phone, a webhook, a cron) INTO
                    an agent. Native messaging does NOT touch this.
  2. AGENT<->AGENT — one agent session talking to another. This is the bucket the
                    native primitives now cover.
  3. FAN-OUT      — one task splitting into many coordinated sub-agents and
                    merging back. Native primitives are the substrate here; your
                    orchestration script sits on top and still earns its keep.

Runs anywhere Claude Code is installed. Stdlib only, read-only, no network.

Usage:  python3 probe.py            # human table
        python3 probe.py --json     # machine-readable
"""
import json
import os
import re
import subprocess
import sys

# Common changelog locations across installs. First hit wins.
CHANGELOG_CANDIDATES = [
    "~/.claude/cache/changelog.md",
    "~/.config/claude/changelog.md",
    "~/Library/Caches/claude/changelog.md",
]

# Each primitive: a signature we grep for in the changelog (a stable phrase from
# the release notes), the bucket it serves, the bespoke plumbing it retires, and
# an honest verdict. `signature` is a lowercased substring match — deliberately
# loose so it survives minor wording drift, tight enough not to false-positive.
PRIMITIVES = [
    {
        "id": "cross_session_sendmessage",
        "title": "Cross-session SendMessage + ListAgents",
        "signature": "message each other",
        "bucket": "AGENT<->AGENT",
        "retires": "Hand-rolled agent-to-agent message bus (HTTP inbox between "
                   "sessions, shell scripts that shell out to another agent).",
        "verdict": "MIGRATE",
        "note": "Sessions discover each other with ListAgents and message by "
                "name, on any of your machines. This is the real replacement "
                "for bespoke session-to-session wiring.",
    },
    {
        "id": "permission_classified_messages",
        "title": "Permission-classified inbound messages",
        "signature": "evaluated by the permission classifier before dispatch",
        "bucket": "AGENT<->AGENT",
        "retires": "Custom allow-listing / auth on your own message endpoint to "
                   "stop one agent driving another unsafely.",
        "verdict": "MIGRATE",
        "note": "Messages to another session are classified before delivery, and "
                "messages to a bypass-permissions session are held for approval "
                "(crossSessionInbound / dialogExpiry settings).",
    },
    {
        "id": "fork_skills_background",
        "title": "context:fork skills run in background",
        "signature": "context: fork",
        "bucket": "FAN-OUT",
        "retires": "Manually detaching a skill/subtask so it does not block the "
                   "main conversation.",
        "verdict": "KEEP+TUNE",
        "note": "Forked skills background by default (opt out with "
                "background:false). Your orchestration keeps working; just drop "
                "the manual detach.",
    },
    {
        "id": "nested_subagents",
        "title": "Nested subagents (depth > 1)",
        "signature": "spawn nested subagents",
        "bucket": "FAN-OUT",
        "retires": "Flattening a naturally-nested fan-out into one layer because "
                   "sub-agents could not themselves spawn.",
        "verdict": "KEEP+TUNE",
        "note": "Depth is capped and configurable "
                "(CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH). Check the default on "
                "your version before relying on deep nesting.",
    },
    {
        "id": "concurrency_cap",
        "title": "Concurrent-subagent cap",
        "signature": "concurrently-running subagents",
        "bucket": "FAN-OUT",
        "retires": "Your own semaphore to stop one message fanning out unbounded "
                   "agents.",
        "verdict": "KEEP+TUNE",
        "note": "Default cap exists (CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS). If "
                "your workflow assumed unlimited parallelism, it is now bounded.",
    },
    {
        "id": "spawn_cap_removed",
        "title": "200-subagent lifetime cap removed",
        "signature": "removed the 200-subagent",
        "bucket": "FAN-OUT",
        "retires": "Restarting a long session to dodge the old lifetime spawn "
                   "ceiling.",
        "verdict": "KEEP+TUNE",
        "note": "Long-running sessions no longer refuse new agents; concurrency "
                "and depth limits still apply.",
    },
]

# INGRESS is listed explicitly as the bucket native primitives do NOT cover, so
# the map is honest about what stays yours.
INGRESS_NOTE = {
    "bucket": "INGRESS",
    "retires": "Nothing. An external event source (phone share-sheet, webhook, "
               "cron, email watcher) still needs your own endpoint to land it "
               "in an agent.",
    "verdict": "KEEP",
    "note": "Cross-session messaging is agent-to-agent only. If a device or "
            "third-party service outside Claude Code has to reach an agent, that "
            "intake stays bespoke. Do not retire it because messaging shipped.",
}


def expand(p):
    return os.path.expanduser(p)


def detect_version():
    try:
        out = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
        m = re.search(r"(\d+\.\d+\.\d+)", out)
        return m.group(1) if m else (out or "unknown")
    except Exception:
        return "unknown (claude not on PATH)"


def load_changelog():
    for cand in CHANGELOG_CANDIDATES:
        path = expand(cand)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                return path, f.read().lower()
    return None, ""


def probe():
    version = detect_version()
    path, changelog = load_changelog()
    results = []
    for prim in PRIMITIVES:
        present = prim["signature"] in changelog if changelog else None
        results.append({**prim, "present": present})
    return {
        "claude_version": version,
        "changelog_path": path,
        "changelog_found": bool(changelog),
        "primitives": results,
        "ingress": INGRESS_NOTE,
    }


def render(data):
    v = data["claude_version"]
    print(f"\n  Claude Code: {v}")
    if not data["changelog_found"]:
        print("  changelog not found — detection is version-name only.")
        print("  (looked in: " + ", ".join(CHANGELOG_CANDIDATES) + ")")
    else:
        print(f"  changelog:   {data['changelog_path']}")

    order = ["INGRESS", "AGENT<->AGENT", "FAN-OUT"]
    rows = []
    ing = data["ingress"]
    rows.append((ing["bucket"], "external intake", "n/a", ing["verdict"]))
    for prim in data["primitives"]:
        if prim["present"] is True:
            mark = "yes"
        elif prim["present"] is False:
            mark = "no"
        else:
            mark = "?"
        rows.append((prim["bucket"], prim["title"], mark, prim["verdict"]))

    rows.sort(key=lambda r: order.index(r[0]) if r[0] in order else 99)

    print()
    print(f"  {'BUCKET':<15}{'PRIMITIVE':<42}{'HAVE':<6}{'VERDICT'}")
    print("  " + "-" * 76)
    for bucket, title, mark, verdict in rows:
        title = (title[:39] + "...") if len(title) > 42 else title
        print(f"  {bucket:<15}{title:<42}{mark:<6}{verdict}")

    print()
    print("  VERDICT KEY")
    print("  KEEP       native primitives do not touch this — it stays yours")
    print("  MIGRATE    a native primitive now does this; retire the bespoke one")
    print("  KEEP+TUNE  native substrate improved; keep your orchestration, "
          "adjust to new caps")
    print()
    print("  The one line to remember: native messaging replaces agent-to-agent")
    print("  wiring, NOT your external intake and NOT your fan-out orchestration.")
    print("  Separate the three before you rip anything out.\n")


def main():
    data = probe()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2))
    else:
        render(data)


if __name__ == "__main__":
    main()
