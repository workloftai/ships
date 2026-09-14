#!/usr/bin/env python3
"""Tests for harness_loop. Stdlib only, no API calls."""
import os, tempfile, unittest
import harness_loop as hl


class TestLocalise(unittest.TestCase):
    def rows(self):
        r = []
        # bad-skill: 6 runs, 5 fail
        for i in range(6):
            r.append({"instruction": "bad-skill", "passed": i == 0})
        # ok-skill: 6 runs, 1 fail
        for i in range(6):
            r.append({"instruction": "ok-skill", "passed": i != 0})
        # rare-skill: 2 runs, both fail, but below min_runs
        for _ in range(2):
            r.append({"instruction": "rare-skill", "passed": False})
        return r

    def test_ranks_worst_eligible_first(self):
        ranked = hl.localise(self.rows(), min_runs=5)
        self.assertEqual(ranked[0]["instruction"], "bad-skill")
        self.assertEqual(ranked[0]["failures"], 5)

    def test_min_runs_gate(self):
        ranked = hl.localise(self.rows(), min_runs=5)
        rare = next(d for d in ranked if d["instruction"] == "rare-skill")
        self.assertFalse(rare["eligible"])  # 2 runs < 5, cannot be the culprit
        # a 100% fail rate below the sample floor must not outrank the real culprit
        self.assertNotEqual(ranked[0]["instruction"], "rare-skill")

    def test_fail_rate(self):
        ranked = hl.localise(self.rows(), min_runs=5)
        ok = next(d for d in ranked if d["instruction"] == "ok-skill")
        self.assertAlmostEqual(ok["fail_rate"], round(1 / 6, 3))


class TestTraces(unittest.TestCase):
    def test_only_failures_for_that_instruction(self):
        rows = [
            {"instruction": "a", "input": "x", "expected": "1", "got": "2", "passed": False},
            {"instruction": "a", "input": "y", "expected": "1", "got": "1", "passed": True},
            {"instruction": "b", "input": "z", "expected": "1", "got": "9", "passed": False},
        ]
        t = hl.failing_traces(rows, "a")
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]["input"], "x")


class TestGate(unittest.TestCase):
    def test_writes_inside_out_dir(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "proposals")
            path = hl.write_proposal(
                out, "extract-postcode", "old text",
                {"revised_instruction": "new", "rationale": "why", "source": "test"},
                [{"input": "i", "expected": "e", "got": "g"}])
            self.assertTrue(os.path.realpath(path).startswith(os.path.realpath(out)))
            with open(path) as fh:
                self.assertIn("PROPOSAL ONLY", fh.read())

    def test_refuses_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "proposals")
            os.makedirs(out)
            with self.assertRaises(ValueError):
                hl.write_proposal(
                    out, "../../escape", "old",
                    {"revised_instruction": "n", "rationale": "r", "source": "t"}, [])


class TestRegressionGuard(unittest.TestCase):
    def rows(self):
        return [
            {"instruction": "x", "input": "a", "expected": "A", "passed": True},
            {"instruction": "x", "input": "b", "expected": "B", "passed": True},
            {"instruction": "x", "input": "c", "expected": "C", "got": "wrong", "passed": False},
            {"instruction": "y", "input": "d", "expected": "D", "passed": True},
        ]

    def test_passing_cases_only_that_instruction(self):
        p = hl.passing_cases(self.rows(), "x")
        self.assertEqual({c["input"] for c in p}, {"a", "b"})

    def test_verify_flags_regressions(self):
        passing = [{"input": "a", "expected": "A"}, {"input": "b", "expected": "B"}]
        # executor that breaks case "b"
        def exec_bad(instruction, inp):
            return "A" if inp == "a" else "BROKEN"
        reg = hl.verify_rewrite("rewrite", passing, exec_bad)
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg[0]["input"], "b")
        self.assertEqual(reg[0]["got"], "BROKEN")

    def test_verify_safe_when_none_break(self):
        passing = [{"input": "a", "expected": "A"}]
        reg = hl.verify_rewrite("rewrite", passing, lambda i, x: "A")
        self.assertEqual(reg, [])

    def test_proposal_verdict_reflects_regressions(self):
        import tempfile
        prop = {"revised_instruction": "n", "rationale": "r", "source": "t"}
        with tempfile.TemporaryDirectory() as d:
            safe = hl.write_proposal(d, "x", "old", prop, [], regressions=[])
            with open(safe) as fh:
                self.assertIn("SAFE", fh.read())
            broke = hl.write_proposal(d, "y", "old", prop, [],
                                      regressions=[{"input": "b", "expected": "B", "got": "X"}])
            with open(broke) as fh:
                self.assertIn("NEEDS REVISION", fh.read())


class TestReadLog(unittest.TestCase):
    def test_skips_malformed_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write('{"instruction": "a", "passed": true}\n')
            f.write('not json\n')
            f.write('{"instruction": "b", "passed": false}\n')
            name = f.name
        try:
            rows = hl.read_log(name)
            self.assertEqual(len(rows), 2)
        finally:
            os.unlink(name)


if __name__ == "__main__":
    unittest.main()
