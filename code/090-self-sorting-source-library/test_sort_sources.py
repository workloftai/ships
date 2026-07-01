#!/usr/bin/env python3
"""
Deterministic tests for sort_sources.py. Stdlib only, no framework.
Builds a scratch library in a temp dir, runs scan / apply / check, asserts.
Run: python3 test_sort_sources.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "sort_sources.py")

CONVENTION = """# Sources

## Prefixes
- `REF` — reference material
- `DATA` — raw research outputs
- `BG` — background reading
- `DRAFT` — my own writing
"""


def run(*args, cwd):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=cwd, capture_output=True, text=True,
    )


def main():
    failures = []

    def ok(cond, msg):
        if cond:
            print(f"  ok: {msg}")
        else:
            print(f"  FAIL: {msg}")
            failures.append(msg)

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "CLAUDE.md"), "w") as fh:
            fh.write(CONVENTION)
        # Two unprefixed files, one already prefixed.
        for name in ["checkout funnel notes.txt", "quarterly.csv", "REF Existing.pdf"]:
            open(os.path.join(d, name), "w").close()

        # scan finds exactly the two unprefixed files
        r = run("scan", cwd=d)
        ok(r.returncode == 0, "scan exits 0")
        data = json.loads(r.stdout)
        unp = {x["name"] for x in data["unprefixed"]}
        ok(unp == {"checkout funnel notes.txt", "quarterly.csv"},
           "scan lists the two unprefixed files")
        ok({x["name"] for x in data["prefixed"]} == {"REF Existing.pdf"},
           "scan recognises the already-prefixed file")
        ok(data["prefixes"] == ["DRAFT", "DATA", "REF", "BG"],
           "prefixes parsed longest-first from convention")

        # check fails while unprefixed files remain
        ok(run("check", cwd=d).returncode == 1, "check exits 1 with unprefixed files")

        # apply an approved map
        mp = {
            "checkout funnel notes.txt": {"prefix": "DRAFT", "title": "Checkout funnel notes"},
            "quarterly.csv": {"prefix": "DATA", "title": "Quarterly"},
        }
        with open(os.path.join(d, ".map.json"), "w") as fh:
            json.dump(mp, fh)

        # dry run changes nothing
        run("apply", "--map", ".map.json", "--dry-run", cwd=d)
        ok(os.path.exists(os.path.join(d, "quarterly.csv")),
           "dry run does not rename")

        r = run("apply", "--map", ".map.json", cwd=d)
        ok(r.returncode == 0, "apply exits 0")
        ok(os.path.exists(os.path.join(d, "DRAFT Checkout funnel notes.txt")),
           "file renamed to canonical form")
        ok(os.path.exists(os.path.join(d, "DATA Quarterly.csv")),
           "second file renamed")
        ok(os.path.exists(os.path.join(d, ".sources.log")),
           "audit log written")

        # check now passes
        ok(run("check", cwd=d).returncode == 0, "check exits 0 after sorting")

        # idempotent: re-applying the same map is a no-op skip
        # (targets already exist; map now keyed on new names would be needed —
        #  here we prove re-running apply on a fully-sorted folder finds nothing new)
        r2 = run("scan", cwd=d)
        ok(len(json.loads(r2.stdout)["unprefixed"]) == 0,
           "no unprefixed files remain")

        # no-clobber: two files wanting the same target name
        for name in ["a.txt", "b.txt"]:
            open(os.path.join(d, name), "w").close()
        clash = {
            "a.txt": {"prefix": "REF", "title": "Same"},
            "b.txt": {"prefix": "REF", "title": "Same"},
        }
        with open(os.path.join(d, ".clash.json"), "w") as fh:
            json.dump(clash, fh)
        run("apply", "--map", ".clash.json", cwd=d)
        ok(os.path.exists(os.path.join(d, "REF Same.txt")) and
           os.path.exists(os.path.join(d, "REF Same (2).txt")),
           "collision resolved without clobber")

        # unknown prefix is rejected, not applied
        open(os.path.join(d, "c.txt"), "w").close()
        with open(os.path.join(d, ".bad.json"), "w") as fh:
            json.dump({"c.txt": {"prefix": "NOPE", "title": "x"}}, fh)
        rbad = run("apply", "--map", ".bad.json", cwd=d)
        ok(rbad.returncode == 1 and os.path.exists(os.path.join(d, "c.txt")),
           "unknown prefix rejected, file untouched")

    print()
    if failures:
        print(f"{len(failures)} test(s) failed")
        sys.exit(1)
    print("all tests passed")


if __name__ == "__main__":
    main()
