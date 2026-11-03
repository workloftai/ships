import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import signal_finder as sf  # noqa: E402

FX = HERE / "fixtures"
quiet = lambda *_: None


class Parsing(unittest.TestCase):
    def test_vtt_timestamps(self):
        s = sf.load_source(str(FX / "sample-talk.vtt"), "S1", "cmd", "en")
        self.assertEqual(s.segments[0].start, 1.0)
        self.assertEqual(s.date, "2026-03-02")

    def test_bracket_lines(self):
        segs = sf.parse_transcript_text("[00:05] hello there\n[1:02:03] later on")
        self.assertEqual([x.start for x in segs], [5.0, 3723.0])

    def test_rolling_captions_deduped(self):
        segs = sf.dedupe_rolling([sf.Segment(0, "a b"), sf.Segment(1, "a b c d")])
        self.assertEqual([x.text for x in segs], ["a b", "c d"])

    def test_chunking_keeps_everything(self):
        s = sf.load_source(str(FX / "sample-talk.vtt"), "S1", "cmd", "en")
        chunks = sf.chunk(s, max_chars=120)
        self.assertGreater(len(chunks), 1)
        self.assertIn("one owner per metric", " ".join(chunks))


class VerbatimGuard(unittest.TestCase):
    def setUp(self):
        self.s = sf.load_source(str(FX / "sample-talk.vtt"), "S1", "cmd", "en")

    def test_real_quote_found_with_timestamp(self):
        ok, ts = self.s.locate("My rule now is one owner per metric")
        self.assertTrue(ok)
        self.assertEqual(ts, 65.0)

    def test_quote_across_segments_and_punctuation(self):
        ok, _ = self.s.locate("measure it. Don't build the dashboard")
        self.assertTrue(ok)

    def test_paraphrase_rejected(self):
        ok, _ = self.s.locate("My rule is that every metric needs exactly one owner")
        self.assertFalse(ok)

    def test_too_short_rejected(self):
        self.assertFalse(self.s.locate("one owner")[0])


class FakeLLM:
    """Returns an invented quote to prove the code drops it."""
    calls = tokens_in = tokens_out = 0

    def json(self, system, user, schema, effort=None):
        if system.startswith("SIGNALS"):
            return {"candidates": [{"quote": "We are about to raise a huge Series B and hire fifty engineers", "about": "x", "said_by_person": True}]}
        if system.startswith("PICK"):
            return {"chosen": "C1", "why": "", "implication": "", "signal_phrase": "your funding news"}
        if system.startswith("EXTRACT"):
            return {"items": [{"kind": "tactic", "statement": "x", "quote": "a sentence that was never said in the talk at all"}]}
        return {"title": "t", "summary": "s", "principles": [{"text": "p", "support": ["I1", "I99"]}],
                "steps": [{"text": "ghost", "support": ["I99"]}], "quotes": ["I1"], "contradictions": []}


class NoInventedPersonalisation(unittest.TestCase):
    def setUp(self):
        self.srcs = [sf.load_source(str(FX / "sample-talk.vtt"), "S1", "cmd", "en")]

    def test_invented_signal_gives_no_opener(self):
        r = sf.run_signal("Sam Example", "Example Labs", self.srcs, FakeLLM(), quiet)
        self.assertIsNone(r["opener"])
        self.assertIn("No verified public signal", r["reason"])

    def test_person_not_in_source_gives_no_opener(self):
        r = sf.run_signal("Nobody Real", "Nowhere Ltd", self.srcs, sf.Offline(), quiet)
        self.assertIsNone(r["opener"])

    def test_offline_signal_opener_shape(self):
        r = sf.run_signal("Sam Example", "Example Labs", self.srcs, sf.Offline(), quiet)
        self.assertTrue(r["opener"].startswith("Hey Sam, thanks for connecting. I saw "))
        self.assertTrue(r["opener"].endswith("which is exactly what I wanted to ask you about."))
        self.assertTrue(self.srcs[0].locate(r["signal"]["quote"])[0])

    def test_playbook_drops_invented_quotes_and_ghost_ids(self):
        r = sf.run_playbook(self.srcs, FakeLLM(), quiet)
        self.assertEqual(r["syn"]["quotes"], [])
        self.assertEqual(r["syn"]["steps"], [])
        self.assertEqual(r["stats"]["quotes_dropped"], 1)


if __name__ == "__main__":
    unittest.main()
