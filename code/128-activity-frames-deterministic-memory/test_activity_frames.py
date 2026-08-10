"""
test_activity_frames.py — unit tests for the deterministic compiler.
Run: python3 test_activity_frames.py   (no pytest needed)
"""
from activity_frames import (
    RawEvent, compile_frames, content_hash, frames_to_json,
    answer, detect_routines, replay, _ranges, _classify, IDLE_GAP_S,
)

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def test_empty():
    check("empty stream -> no frames", compile_frames([]) == [])


def test_single_run_one_frame():
    rows = [RawEvent(t, "vscode", "", "f.py", keystrokes=1) for t in range(10)]
    frames = compile_frames(rows)
    check("contiguous same-app run = 1 frame", len(frames) == 1)
    check("duration is inclusive of sampled seconds", frames[0].duration_s == 10)
    check("keystrokes aggregated", frames[0].keystrokes == 10)
    check("evidence is one compact range", frames[0].evidence == [[0, 9]])


def test_app_change_splits():
    rows = [RawEvent(0, "vscode", "", "a"), RawEvent(1, "slack", "", "b")]
    frames = compile_frames(rows)
    check("app change starts a new frame", len(frames) == 2)


def test_site_change_splits():
    rows = [RawEvent(0, "chrome", "github.com", "a"),
            RawEvent(1, "chrome", "stackoverflow.com", "b")]
    frames = compile_frames(rows)
    check("site change starts a new frame", len(frames) == 2)


def test_idle_gap_splits():
    rows = [RawEvent(0, "vscode", "", "a"),
            RawEvent(IDLE_GAP_S + 5, "vscode", "", "a")]
    frames = compile_frames(rows)
    check("idle gap > threshold splits same-app frame", len(frames) == 2)


def test_subthreshold_gap_merges():
    rows = [RawEvent(0, "vscode", "", "a"), RawEvent(IDLE_GAP_S - 1, "vscode", "", "a")]
    frames = compile_frames(rows)
    check("sub-threshold gap keeps one frame", len(frames) == 1)


def test_typing_deterministic():
    rows = [RawEvent(t, "vscode", "", "f.py", keystrokes=1) for t in range(50)]
    h1 = content_hash(compile_frames(rows))
    h2 = content_hash(compile_frames(list(reversed(rows))))  # input order shuffled
    check("byte-identical hash regardless of input order", h1 == h2)


def test_classify_rules():
    check("slack -> communication", _classify("slack", "") == "communication")
    check("github domain -> browsing_docs", _classify("chrome", "github.com") == "browsing_docs")
    check("unknown -> other", _classify("weirdapp", "") == "other")


def test_ranges():
    check("ranges collapse consecutive", _ranges([0, 1, 2, 5, 6, 9]) == [[0, 2], [5, 6], [9, 9]])
    check("ranges handle empty", _ranges([]) == [])


def test_answer_duration():
    rows = ([RawEvent(t, "vscode", "", "f") for t in range(60)])
    frames = compile_frames(rows)
    check("how long on app is exact", answer(frames, "how long on vscode?") == "1m 0s")


def test_answer_point_in_time():
    rows = [RawEvent(t, "slack", "", "chat") for t in range(30)]
    frames = compile_frames(rows)
    check("point-in-time lookup finds frame", "slack" in answer(frames, "what was i doing at time 10?"))
    check("point-in-time miss is reported",
          "no activity" in answer(frames, "what was i doing at time 9999?"))


def test_routine_and_replay():
    def day():
        seq = [("vscode", ""), ("slack", ""), ("gmail", "")]
        rows, t = [], 0
        for app, site in seq:
            for _ in range(5):
                rows.append(RawEvent(t, app, site, "x")); t += 1
            t += 5
        return compile_frames(rows)
    routines = detect_routines([day(), day(), day()], n=3, min_days=2)
    check("recurrent routine detected across days", len(routines) >= 1)
    check("top routine recurs on all 3 days", routines[0]["recurrence"] == 3)
    steps = replay(routines[0])
    check("replay emits one step per frame", len(steps) == 3)


def test_evidence_is_auditable():
    rows = [RawEvent(t, "vscode", "", "f", keystrokes=1) for t in range(20)]
    frames = compile_frames(rows)
    # Reconstruct covered rows from evidence ranges; must equal the raw run.
    covered = []
    for a, b in frames[0].evidence:
        covered.extend(range(a, b + 1))
    check("evidence ranges point back to every raw row", covered == list(range(20)))


if __name__ == "__main__":
    for fn in sorted(k for k in dict(globals()) if k.startswith("test_")):
        print(fn)
        globals()[fn]()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
