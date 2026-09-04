#!/usr/bin/env python3
"""
Tests for chain_check.py. No test framework needed: run `python3 test_chain_check.py`.
Exits 0 if all pass, 1 on first failure.
"""
import tempfile
from pathlib import Path

import chain_check as cc

PASSED = 0


def ok(cond, msg):
    global PASSED
    if not cond:
        raise AssertionError(msg)
    PASSED += 1


def write(d: Path, name: str, body: str):
    (d / name).write_text(body)


def fresh_chain(d: Path):
    """A minimal, unsealed intent -> spec -> plan chain."""
    write(d, "intent.md", "---\nstage: intent\n---\n# Intent\nBuild dark mode.\n")
    write(d, "spec.md",
          "---\nstage: spec\nparent: intent.md\nparent_sha256:\n---\n# Spec\nA toggle.\n")
    write(d, "plan.md",
          "---\nstage: plan\nparent: spec.md\nparent_sha256:\n---\n# Plan\nEdit theme.ts.\n")


def test_unsealed_is_broken():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        good, results = cc.check(d)
        ok(good is False, "unsealed chain should be broken (no parent_sha256)")
        reasons = [r.get("reason", "") for r in results]
        ok(any("never sealed" in r for r in reasons), "should report 'never sealed'")


def test_sealed_is_intact():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        cc.seal(d)
        good, _ = cc.check(d)
        ok(good is True, "sealed chain should be intact")


def test_tampered_upstream_snaps():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        cc.seal(d)
        # Edit the intent AFTER sign-off. The spec's sealed hash no longer matches.
        write(d, "intent.md", "---\nstage: intent\n---\n# Intent\nBuild LIGHT mode.\n")
        good, results = cc.check(d)
        ok(good is False, "editing a sealed upstream artifact should snap the chain")
        spec = next(r for r in results if r["artifact"] == "spec.md")
        ok(spec["status"] == "broken", "spec link should be the broken one")
        ok("changed since sign-off" in spec["reason"], "should name the real cause")


def test_missing_parent_fails():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        cc.seal(d)
        (d / "intent.md").unlink()
        good, results = cc.check(d)
        ok(good is False, "a missing parent should fail the chain")


def test_reseal_after_legit_change():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        cc.seal(d)
        write(d, "intent.md", "---\nstage: intent\n---\n# Intent\nBuild dark mode v2.\n")
        ok(cc.check(d)[0] is False, "chain should snap after the edit")
        cc.seal(d)  # human reviews and re-signs
        ok(cc.check(d)[0] is True, "re-sealing after review should restore the chain")


def test_hash_ignores_front_matter_and_trailing_newline():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        fresh_chain(d)
        cc.seal(d)
        # Add a front-matter key and a trailing newline to the parent: body is same.
        (d / "intent.md").write_text(
            "---\nstage: intent\nreviewer: alfred\n---\n# Intent\nBuild dark mode.\n\n\n")
        ok(cc.check(d)[0] is True,
           "front-matter edits and trailing newlines must not snap the chain")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"pass  {name}")
    print(f"\n{PASSED} assertions passed")
