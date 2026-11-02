#!/usr/bin/env python3
"""Verdict for skill-gate.sh: reads a SkillSpector JSON report on stdin.
Exit 0 pass, 1 block (any HIGH/CRITICAL that is not vendored-dep SC9), 2 error."""
import json
import sys

VENDORED_SUFFIXES = ("bun.lockb", "bun.lock", "package-lock.json")


def main():
    try:
        d = json.load(sys.stdin)
    except Exception as e:  # fail closed
        print(f"skill-gate: unparseable report ({e})", file=sys.stderr)
        return 2
    ra = d.get("risk_assessment") or {}
    block, vend = [], 0
    for i in d.get("issues", []):
        sev = (i.get("severity") or "").upper()
        if sev not in ("HIGH", "CRITICAL"):
            continue
        loc = i.get("location") or {}
        f = loc.get("file") or ""
        if i.get("id") == "SC9" and ("node_modules/" in f or f.endswith(VENDORED_SUFFIXES)):
            vend += 1
            continue
        block.append(f"  {sev:8} {i.get('id'):5} {f}:{loc.get('start_line')}  {i.get('pattern')}")
    target = sys.argv[1] if len(sys.argv) > 1 else "?"
    print(f"skill-gate: {target}")
    print(f"  risk {ra.get('score')} {ra.get('severity')} -> {ra.get('recommendation')}; "
          f"{len(block)} high/critical, {vend} vendored-dep SC9 (not blocking)")
    for b in block:
        print(b)
    if block:
        print("  BLOCK: review before installing")
        return 1
    print("  PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
