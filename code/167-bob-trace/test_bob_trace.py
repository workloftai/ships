#!/usr/bin/env python3
"""Tests for bob-trace. Stdlib unittest, no external deps."""
import json
import os
import tempfile
import unittest

import bob_trace as bt


def _write_job(d, jid, job, log=""):
    with open(os.path.join(d, jid + ".json"), "w") as f:
        json.dump(job, f)
    with open(os.path.join(d, jid + ".log"), "w") as f:
        f.write(log)


class TestMineLog(unittest.TestCase):
    def test_counts_errors_retries_http(self):
        m = bt.mine_log([
            "starting run",
            "Traceback (most recent call last):",
            "ValueError: boom",
            "retrying request (attempt 2)",
            "got HTTP 429, backoff 4s",
            "server returned 503",
            "done",
        ])
        self.assertGreaterEqual(m["error_count"], 2)
        self.assertGreaterEqual(m["retries"], 2)
        self.assertEqual(m["http_errors"], 2)  # 429 + 503

    def test_tokens_and_cost(self):
        m = bt.mine_log([
            "prompt used 12,345 tokens",
            "completion: 6789 tokens",
            "total cost: $0.4210",
        ])
        self.assertEqual(m["tokens"], 12345 + 6789)
        self.assertAlmostEqual(m["cost_usd"], 0.4210, places=4)

    def test_models_detected(self):
        m = bt.mine_log(["calling claude-opus-4-8", "fallback to deepseek-v41-flash"])
        self.assertIn("claude-opus-4-8", m["models"])
        self.assertTrue(any("deepseek" in x for x in m["models"]))

    def test_clean_log_no_false_positives(self):
        m = bt.mine_log(["all good", "0 failed", "42 passed", "exit 0"])
        self.assertEqual(m["error_count"], 0)
        self.assertIsNone(m["tokens"])
        self.assertIsNone(m["cost_usd"])


class TestBuildTrace(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._orig = bt.JOBS_DIR
        bt.JOBS_DIR = self.d

    def tearDown(self):
        bt.JOBS_DIR = self._orig

    def test_clean_job_is_ok(self):
        _write_job(self.d, "j1", {
            "id": "j1", "label": "nightly", "cmd": "echo hi", "status": "done",
            "rc": 0, "timeout": 3600,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:01:00+01:00",
            "last_heartbeat": "2026-09-15T07:01:00+01:00",
        }, "hello\ndone\n")
        t = bt.build_trace("j1")
        self.assertEqual(t["verdict"], "ok")
        self.assertEqual(t["duration_s"], 60)

    def test_sigterm_is_terminated(self):
        _write_job(self.d, "j2", {
            "id": "j2", "label": "ab", "cmd": "loop", "status": "failed",
            "rc": -15, "timeout": 21600,
            "started": "2026-09-15T07:56:30+01:00", "ended": "2026-09-15T12:40:04+01:00",
            "last_heartbeat": "2026-09-15T12:39:31+01:00",
        }, "working\nkilled\n")
        t = bt.build_trace("j2")
        self.assertEqual(t["verdict"], "terminated")
        self.assertFalse(t["timed_out"])  # 4h47m run < 6h ceiling

    def test_timeout_detected(self):
        _write_job(self.d, "j3", {
            "id": "j3", "label": "slow", "cmd": "sleep", "status": "failed",
            "rc": -15, "timeout": 60,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:01:00+01:00",
            "last_heartbeat": "2026-09-15T07:01:00+01:00",
        })
        t = bt.build_trace("j3")
        self.assertEqual(t["verdict"], "timed-out")
        self.assertTrue(t["timed_out"])

    def test_heartbeat_stall(self):
        _write_job(self.d, "j4", {
            "id": "j4", "label": "stalled", "cmd": "x", "status": "failed", "rc": 1,
            "timeout": 3600,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:30:00+01:00",
            "last_heartbeat": "2026-09-15T07:10:00+01:00",
        }, "error: died\n")
        t = bt.build_trace("j4")
        self.assertEqual(t["stall_s"], 1200)
        self.assertIn("stalled", t["reason"])

    def test_done_with_errors(self):
        _write_job(self.d, "j5", {
            "id": "j5", "label": "flaky", "cmd": "x", "status": "done", "rc": 0,
            "timeout": 3600,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:05:00+01:00",
            "last_heartbeat": "2026-09-15T07:05:00+01:00",
        }, "Exception: transient\nrecovered\ndone\n")
        t = bt.build_trace("j5")
        self.assertEqual(t["verdict"], "done-with-errors")


class TestSpans(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._orig = bt.JOBS_DIR
        bt.JOBS_DIR = self.d

    def tearDown(self):
        bt.JOBS_DIR = self._orig

    def test_span_id_widths_and_error_flag(self):
        _write_job(self.d, "j6", {
            "id": "j6", "label": "x", "cmd": "c", "status": "failed", "rc": 1,
            "timeout": 3600,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:01:00+01:00",
            "last_heartbeat": "2026-09-15T07:01:00+01:00",
        }, "error: nope\n")
        spans = bt.to_spans(bt.build_trace("j6"))
        root = spans[0]
        self.assertEqual(len(root["trace_id"]), 32)   # 16 bytes hex
        self.assertEqual(len(root["span_id"]), 16)     # 8 bytes hex
        self.assertIsNone(root["parent_span_id"])
        self.assertTrue(root["status_error"])
        self.assertGreater(root["end_ns"], root["start_ns"])
        # child error spans link to root
        for c in spans[1:]:
            self.assertEqual(c["parent_span_id"], root["span_id"])

    def test_emit_appends_to_spool(self):
        _write_job(self.d, "j7", {
            "id": "j7", "label": "x", "cmd": "c", "status": "done", "rc": 0,
            "timeout": 3600,
            "started": "2026-09-15T07:00:00+01:00", "ended": "2026-09-15T07:01:00+01:00",
            "last_heartbeat": "2026-09-15T07:01:00+01:00",
        }, "ok\n")
        spool = os.path.join(self.d, "spans.jsonl")
        n = bt.emit(["j7"], spool=spool)
        self.assertEqual(n, 1)
        lines = [json.loads(l) for l in open(spool)]
        self.assertEqual(lines[0]["attrs"]["service.name"], "bob-bg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
