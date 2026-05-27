import json
import tempfile
import unittest
from pathlib import Path

from daemon.correlation_engine.engine import (
    CorrelationCandidate,
    CorrelationEngine,
    LayerEvent,
    ClipPasteRule,
    ClipDeleteRule,
    EffectChangeRule,
    UndoRule,
)


class ClipPasteRuleTests(unittest.TestCase):
    def test_matches_paste_and_transition(self):
        rule = ClipPasteRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 990, {"probable_operation": "paste"}),
                LayerEvent("audio_buffer", "audio_transition", 1010, {"direction": "silence_to_audio"}),
            ],
        )
        result = rule.evaluate(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.edit_type, "clip_paste")
        self.assertGreaterEqual(result.confidence, 0.80)

    def test_no_match_without_transition(self):
        rule = ClipPasteRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 990, {"probable_operation": "paste"}),
            ],
        )
        self.assertIsNone(rule.evaluate(candidate))


class ClipDeleteRuleTests(unittest.TestCase):
    def test_matches_delete_and_silence(self):
        rule = ClipDeleteRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 990, {"probable_operation": "delete"}),
                LayerEvent("audio_buffer", "audio_transition", 1020, {"direction": "audio_to_silence"}),
            ],
        )
        result = rule.evaluate(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.edit_type, "clip_delete")

    def test_no_match_wrong_direction(self):
        rule = ClipDeleteRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 990, {"probable_operation": "delete"}),
                LayerEvent("audio_buffer", "audio_transition", 1020, {"direction": "silence_to_audio"}),
            ],
        )
        self.assertIsNone(rule.evaluate(candidate))


class EffectChangeRuleTests(unittest.TestCase):
    def test_matches_mixer_and_spectral(self):
        rule = EffectChangeRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("screen_observer", "screen_mixer_changed", 900, {}),
                LayerEvent("audio_buffer", "spectral_shift", 1000, {}),
            ],
        )
        result = rule.evaluate(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.edit_type, "effect_change")

    def test_no_match_if_silence_transition_present(self):
        rule = EffectChangeRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("screen_observer", "screen_mixer_changed", 900, {}),
                LayerEvent("audio_buffer", "spectral_shift", 1000, {}),
                LayerEvent("audio_buffer", "audio_transition", 1000, {"direction": "audio_to_silence"}),
            ],
        )
        self.assertIsNone(rule.evaluate(candidate))


class UndoRuleTests(unittest.TestCase):
    def test_matches_undo_shortcut(self):
        rule = UndoRule()
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 990, {"probable_operation": "undo"}),
                LayerEvent("audio_buffer", "buffer_hash", 1010, {"window_hash": "abc"}),
            ],
        )
        result = rule.evaluate(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.edit_type, "undo")


class CorrelationEngineTests(unittest.TestCase):
    def test_ingest_produces_composite_edits(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "composite.jsonl"
            engine = CorrelationEngine(window_ms=2000, evidence_path=evidence_path)

            engine.ingest(LayerEvent("input_capture", "input_shortcut", 1000, {"probable_operation": "paste"}))
            results = engine.ingest(LayerEvent("audio_buffer", "audio_transition", 1050, {"direction": "silence_to_audio"}))

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].edit_type, "clip_paste")

            lines = evidence_path.read_text().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            written = json.loads(lines[0])
            self.assertEqual(written["event_type"], "composite_edit")
            self.assertEqual(written["edit_type"], "clip_paste")

    def test_expires_old_events(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "composite.jsonl"
            engine = CorrelationEngine(window_ms=500, evidence_path=evidence_path)

            engine.ingest(LayerEvent("input_capture", "input_shortcut", 1000, {"probable_operation": "paste"}))
            results = engine.ingest(LayerEvent("audio_buffer", "audio_transition", 2000, {"direction": "silence_to_audio"}))

            self.assertEqual(len(results), 0)
            self.assertEqual(engine.buffer_size, 1)

    def test_low_confidence_not_emitted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "composite.jsonl"
            engine = CorrelationEngine(window_ms=2000, evidence_path=evidence_path)

            engine.ingest(LayerEvent("audio_buffer", "buffer_hash", 1000, {}))
            results = engine.ingest(LayerEvent("audio_buffer", "buffer_hash", 1050, {}))

            self.assertEqual(len(results), 0)

    def test_alignment_bonus_tight_window(self):
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("input_capture", "input_shortcut", 995, {"probable_operation": "paste"}),
                LayerEvent("audio_buffer", "audio_transition", 1005, {"direction": "silence_to_audio"}),
                LayerEvent("screen_observer", "screen_arrangement_changed", 1010, {}),
            ],
        )
        rule = ClipPasteRule()
        result = rule.evaluate(candidate)
        self.assertIsNotNone(result)
        self.assertGreater(result.confidence, 0.90)


class CorrelationCandidateTests(unittest.TestCase):
    def test_layers_present(self):
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("audio_buffer", "buffer_hash", 1000, {}),
                LayerEvent("input_capture", "input_shortcut", 1000, {}),
                LayerEvent("audio_buffer", "spectral_shift", 1000, {}),
            ],
        )
        self.assertEqual(candidate.layers_present, {"audio_buffer", "input_capture"})

    def test_span_ms(self):
        candidate = CorrelationCandidate(
            window_center_ms=1000,
            events=[
                LayerEvent("a", "x", 900, {}),
                LayerEvent("b", "y", 1100, {}),
            ],
        )
        self.assertEqual(candidate.span_ms, 200)


if __name__ == "__main__":
    unittest.main()
