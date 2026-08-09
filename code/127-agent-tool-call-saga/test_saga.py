#!/usr/bin/env python3
"""Tests for saga. Pure stdlib, no network. Run: python3 -m unittest -v"""
import tempfile
import unittest
from pathlib import Path

from saga import Saga, CompensationError, recover


class InProcessTests(unittest.TestCase):
    def test_happy_path_runs_no_compensation(self):
        undone = []
        with Saga() as s:
            s.step("a", lambda: 1, compensate=lambda: undone.append("a"))
            s.step("b", lambda: 2, compensate=lambda: undone.append("b"))
        self.assertEqual(undone, [])  # committed cleanly, nothing undone

    def test_failure_compensates_in_reverse(self):
        order = []
        with self.assertRaises(ValueError):
            with Saga() as s:
                s.step("a", lambda: order.append("do-a"),
                       compensate=lambda: order.append("undo-a"))
                s.step("b", lambda: order.append("do-b"),
                       compensate=lambda: order.append("undo-b"))
                s.step("c", action=lambda: (_ for _ in ()).throw(ValueError("boom")))
        # a and b are undone, in reverse; c never recorded a compensation
        self.assertEqual(order, ["do-a", "do-b", "undo-b", "undo-a"])

    def test_failing_step_is_not_compensated(self):
        undone = []
        with self.assertRaises(RuntimeError):
            with Saga() as s:
                s.step("a", lambda: None, compensate=lambda: undone.append("a"))
                s.step("b", action=lambda: (_ for _ in ()).throw(RuntimeError()),
                       compensate=lambda: undone.append("b"))
        self.assertEqual(undone, ["a"])  # b's action failed, so b is not undone

    def test_compensation_failure_is_aggregated_not_swallowed(self):
        undone = []

        def bad():
            raise OSError("cannot undo")

        with self.assertRaises(CompensationError) as ctx:
            s = Saga()
            s.step("a", lambda: None, compensate=lambda: undone.append("a"))
            s.step("b", lambda: None, compensate=bad)
            s.rollback()
        # a still got undone even though b's compensation blew up
        self.assertEqual(undone, ["a"])
        self.assertEqual(len(ctx.exception.failures), 1)
        self.assertEqual(ctx.exception.failures[0][0], "b")

    def test_cannot_step_after_finish(self):
        s = Saga()
        s.commit()
        with self.assertRaises(RuntimeError):
            s.step("late", lambda: None)

    def test_non_serialisable_comp_args_rejected_early(self):
        s = Saga()
        with self.assertRaises(TypeError):
            s.step("a", lambda: None, comp_name="x", comp_args={"bad": object()})


class CrashRecoveryTests(unittest.TestCase):
    def _journal(self):
        return str(Path(self.td.name) / "run.jsonl")

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)

    def test_recover_replays_named_compensations_in_reverse(self):
        jp = self._journal()
        # simulate a run that provisioned two things then the process died
        s = Saga(journal_path=jp)
        s.step("create-db", lambda: None, comp_name="drop_db", comp_args={"id": "db1"})
        s.step("create-dns", lambda: None, comp_name="del_dns", comp_args={"host": "a.example"})
        # no commit: the process "crashed" here

        calls = []
        registry = {
            "drop_db": lambda id: calls.append(("drop_db", id)),
            "del_dns": lambda host: calls.append(("del_dns", host)),
        }
        summary = recover(jp, registry)
        self.assertEqual(calls, [("del_dns", "a.example"), ("drop_db", "db1")])
        self.assertEqual(len(summary["recovered"]), 1)

    def test_recover_is_idempotent(self):
        jp = self._journal()
        s = Saga(journal_path=jp)
        s.step("x", lambda: None, comp_name="undo_x", comp_args={})
        calls = []
        registry = {"undo_x": lambda: calls.append("undo_x")}
        recover(jp, registry)
        recover(jp, registry)  # second run must be a no-op
        self.assertEqual(calls, ["undo_x"])

    def test_committed_saga_is_not_recovered(self):
        jp = self._journal()
        s = Saga(journal_path=jp)
        s.step("x", lambda: None, comp_name="undo_x", comp_args={})
        s.commit()
        calls = []
        recover(jp, {"undo_x": lambda: calls.append("undo_x")})
        self.assertEqual(calls, [])

    def test_missing_handler_reported_as_failure(self):
        jp = self._journal()
        s = Saga(journal_path=jp)
        s.step("x", lambda: None, comp_name="undo_x", comp_args={})
        summary = recover(jp, {})  # empty registry
        self.assertEqual(len(summary["failures"]), 1)
        self.assertIn("no handler", summary["failures"][0]["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
