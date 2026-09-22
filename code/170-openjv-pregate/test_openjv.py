"""Unit tests for the OpenJV local logit pre-gate.

No Ollama needed: these cover logprob parsing, calibration, the KILL-only
decision rule, prompt truncation, and the fail-safe path (a dead endpoint must
ABSTAIN, never raise).

    python3 -m unittest -v test_openjv
"""
from __future__ import annotations

import math
import os
import unittest

import openjv


def _tlp(pairs):
    return [{"token": t, "logprob": math.log(p)} for t, p in pairs]


class TestOpenJV(unittest.TestCase):
    def test_option_mass_reads_both(self):
        pk, pp = openjv._option_mass(_tlp([("KILL", 0.8), ("PASS", 0.2)]))
        self.assertAlmostEqual(pk, 0.8, places=6)
        self.assertAlmostEqual(pp, 0.2, places=6)

    def test_option_mass_sums_variants(self):
        pk, pp = openjv._option_mass(
            _tlp([("KILL", 0.5), (" KILL", 0.2), ("Kill", 0.1), ("PASS", 0.2)]))
        self.assertAlmostEqual(pk, 0.8, places=6)
        self.assertAlmostEqual(pp, 0.2, places=6)

    def test_option_mass_missing_is_none(self):
        pk, pp = openjv._option_mass(_tlp([("PASS", 0.9), ("foo", 0.1)]))
        self.assertIsNone(pk)
        self.assertAlmostEqual(pp, 0.9, places=6)

    def test_temp_scale(self):
        self.assertEqual(openjv._temp_scale(0.9, 1.0), 0.9)
        self.assertLess(openjv._temp_scale(0.9, 2.0), 0.9)
        self.assertGreater(openjv._temp_scale(0.9, 0.5), 0.9)

    def test_fail_safe_abstains(self):
        os.environ["VERA_OPENJV_URL"] = "http://127.0.0.1:1"
        try:
            v = openjv.pregate("out", "criteria")
        finally:
            os.environ.pop("VERA_OPENJV_URL", None)
        self.assertEqual(v.verdict, "ABSTAIN")
        self.assertEqual(v.cost_usd, 0.0)
        self.assertIn("error", v.note)

    def test_build_prompt_truncates(self):
        p = openjv.build_prompt("x" * 10_000, "c", max_chars=100)
        self.assertIn("[truncated]", p)

    def test_enabled_flag(self):
        old = os.environ.get("VERA_OPENJV_PREGATE")
        try:
            os.environ["VERA_OPENJV_PREGATE"] = "0"
            self.assertFalse(openjv.enabled())
            os.environ["VERA_OPENJV_PREGATE"] = "1"
            self.assertTrue(openjv.enabled())
        finally:
            if old is None:
                os.environ.pop("VERA_OPENJV_PREGATE", None)
            else:
                os.environ["VERA_OPENJV_PREGATE"] = old


if __name__ == "__main__":
    unittest.main()
