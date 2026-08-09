#!/usr/bin/env python3
"""End-to-end demo. No network. Run: python3 demo.py

Two stories:
  1) A four-step "deploy" where the last step fails, and the three live side
     effects unwind themselves in reverse.
  2) A run that "crashes" mid-way, and a separate recover() call cleans up the
     side effects from its journal, using only named handlers.
"""
import tempfile
from pathlib import Path

from saga import Saga, recover

# A fake world the agent is acting on. In real life these are API calls.
WORLD = {"resources": set(), "dns": set(), "cache": set()}


def show(label):
    print(f"   world after {label}: resources={sorted(WORLD['resources'])} "
          f"dns={sorted(WORLD['dns'])} cache={sorted(WORLD['cache'])}")


def story_one():
    print("1) A deploy that fails on the last step, and unwinds itself")
    print("-" * 68)
    WORLD["resources"].clear(); WORLD["dns"].clear(); WORLD["cache"].clear()
    try:
        with Saga() as s:
            s.step("provision", lambda: WORLD["resources"].add("app-1"),
                   compensate=lambda: WORLD["resources"].discard("app-1"))
            show("provision")
            s.step("dns", lambda: WORLD["dns"].add("app.example"),
                   compensate=lambda: WORLD["dns"].discard("app.example"))
            show("dns")
            s.step("warm-cache", lambda: WORLD["cache"].add("app-1"),
                   compensate=lambda: WORLD["cache"].discard("app-1"))
            show("warm-cache")

            def flip_live():
                raise RuntimeError("health check failed, refusing to go live")
            s.step("go-live", flip_live)  # boom
    except RuntimeError as e:
        print(f"   step 4 failed: {e}")
    print("   -> rollback ran; every side effect is gone:")
    show("rollback")
    assert not (WORLD["resources"] or WORLD["dns"] or WORLD["cache"])


def story_two():
    print("\n2) A run that crashes mid-way, cleaned up from its journal")
    print("-" * 68)
    WORLD["resources"].clear(); WORLD["dns"].clear()
    with tempfile.TemporaryDirectory() as td:
        jp = str(Path(td) / "run.jsonl")

        # the run: it provisions two things, journalling a NAMED compensation for
        # each, then the process "dies" before commit (we just stop here).
        s = Saga(journal_path=jp)
        s.step("provision", lambda: WORLD["resources"].add("app-2"),
               comp_name="deprovision", comp_args={"rid": "app-2"})
        s.step("dns", lambda: WORLD["dns"].add("app2.example"),
               comp_name="del_dns", comp_args={"host": "app2.example"})
        print("   process died after 2 steps, no commit."); show("crash")

        # a separate recovery process starts fresh. It has no closures, only a
        # registry of named handlers and the journal on disk.
        registry = {
            "deprovision": lambda rid: WORLD["resources"].discard(rid),
            "del_dns": lambda host: WORLD["dns"].discard(host),
        }
        summary = recover(jp, registry)
        print(f"   recover() replayed: {summary['recovered']}")
        show("recover")
        # running it again is a no-op, so a retried recovery does not double-undo
        again = recover(jp, registry)
        print(f"   recover() again (idempotent): recovered={again['recovered']}")
    assert not (WORLD["resources"] or WORLD["dns"])


if __name__ == "__main__":
    story_one()
    story_two()
    print("\nDone. Wrap your agent's risky tool calls in a Saga and a failed run "
          "cleans up after itself.")
