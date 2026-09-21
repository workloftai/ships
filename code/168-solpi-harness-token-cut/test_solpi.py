"""Tests for the SoL-Pi mechanisms and the loop simulator.

Run:  python3 -m unittest -v test_solpi
"""
import unittest

import harness
import solpi
from harness import Step, run
from solpi import Observation, ntok


BIG = "line of source code\n" * 2000          # ~38 KiB, over the pack threshold
SMALL = "short output\n"                        # under every threshold
LOG = ("$ python3 -m unittest\n"
       + "ok\n" * 500
       + "FAIL: test_x\nTraceback (most recent call last):\n"
         "AssertionError: 1 != 2\n"
       + "trailing\n" * 500)                     # > 4 KiB, from an allowlisted cmd


class TestTokenizer(unittest.TestCase):
    def test_ntok_positive(self):
        self.assertGreater(ntok("hello world"), 0)


class TestObservationPack(unittest.TestCase):
    def test_full_then_excerpt(self):
        o = Observation("file", "cat big.py", BIG, subtask=0, added_at=1)
        self.assertEqual(o.mechanism, "pack")
        first = o.render(1, set(), set())
        second = o.render(2, set(), set())
        third = o.render(3, set(), set())
        self.assertEqual(first, o.full_text)          # request 1: full
        self.assertEqual(second, o.full_text)          # request 2: full
        self.assertLess(ntok(third), ntok(o.full_text))  # request 3: shrunk
        self.assertIn(o.handle, third)                 # handle present for retrieval

    def test_small_output_untouched(self):
        o = Observation("file", "cat tiny.py", SMALL, subtask=0, added_at=1)
        self.assertEqual(o.mechanism, "plain")
        self.assertEqual(o.render(9, set(), set()), o.full_text)


class TestEvidenceReducer(unittest.TestCase):
    def test_receipt_smaller_and_keeps_signals(self):
        o = Observation("log", "python3 -m unittest", LOG, subtask=0, added_at=1)
        self.assertEqual(o.mechanism, "reduce")
        r = o.render(1, set(), set())
        self.assertLess(ntok(r), ntok(o.full_text))    # verified shrink
        self.assertIn("AssertionError: 1 != 2", r)     # signal preserved
        self.assertIn("exit=failure", r)               # exit status parsed

    def test_non_allowlisted_command_not_reduced(self):
        o = Observation("log", "curl https://example.com", LOG, subtask=0, added_at=1)
        self.assertNotEqual(o.mechanism, "reduce")


class TestRetrieval(unittest.TestCase):
    def test_open_handle_returns_exact_bytes(self):
        o = Observation("file", "cat big.py", BIG, subtask=0, added_at=1)
        packed = o.render(5, set(), set())
        exact = o.render(5, {o.handle}, set())
        self.assertLess(ntok(packed), ntok(exact))
        self.assertEqual(exact, o.full_text)           # retrieval is byte-exact


class TestCompactionGate(unittest.TestCase):
    def test_summary_line_is_small(self):
        o = Observation("file", "cat big.py", BIG, subtask=0, added_at=1)
        self.assertLess(ntok(o._summary_line()), 60)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.traj = [
            Step("tool", "log", "python3 -m unittest", LOG, subtask=0),
            Step("tool", "file", "cat big.py", BIG, subtask=0),
            Step("boundary", subtask_done=0),
            Step("tool", "note", "reason", "thinking\n", subtask=1),
            Step("edit_verify", command="edit && python3 -m unittest",
                 text="ok\nRan 1 test OK\n", subtask=1),
            Step("answer"),
        ]

    def test_solpi_uses_fewer_tokens(self):
        naive = run(self.traj, "naive")
        sol = run(self.traj, "solpi")
        self.assertLess(sol["cum_input_tokens"], naive["cum_input_tokens"])

    def test_action_fusion_removes_a_request(self):
        naive = run(self.traj, "naive")
        sol = run(self.traj, "solpi")
        self.assertEqual(sol["requests"], naive["requests"] - 1)

    def test_no_evidence_lost(self):
        sol = run(self.traj, "solpi")
        archive = "\n".join(o.full_text for o in sol["observations"])
        self.assertIn("AssertionError: 1 != 2", archive)

    def test_disabling_all_mechanisms_matches_naive_tokens(self):
        # solpi with every mechanism off should equal naive on token count
        naive = run(self.traj, "naive")
        old_p, old_r = solpi.PACK_THRESHOLD, solpi.REDUCE_THRESHOLD
        solpi.PACK_THRESHOLD = solpi.REDUCE_THRESHOLD = 10**12
        sol = run(self.traj, "solpi", fuse=False, compact_on=False)
        solpi.PACK_THRESHOLD, solpi.REDUCE_THRESHOLD = old_p, old_r
        # naive renders add a tiny per-obs header; allow a small tolerance
        self.assertLess(abs(sol["cum_input_tokens"] - naive["cum_input_tokens"]),
                        0.02 * naive["cum_input_tokens"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
