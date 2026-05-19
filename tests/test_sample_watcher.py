import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from daemon.sample_watcher.watcher import (
    build_sample_file_event,
    is_audio_file,
    observe_existing_files,
)


class SampleWatcherTests(unittest.TestCase):
    def test_builds_directly_observed_wav_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_path = Path(tmp_dir) / "example.wav"
            _write_test_wav(sample_path)

            event = build_sample_file_event(sample_path, observed_at="2026-05-19T00:00:00Z")

            self.assertEqual(event["event_type"], "sample_file_observed")
            self.assertEqual(event["proof_level"], "directly_observed")
            self.assertEqual(event["file_name"], "example.wav")
            self.assertEqual(event["format"], "wav")
            self.assertEqual(event["file_extension"], ".wav")
            self.assertEqual(event["sha256"], hashlib.sha256(sample_path.read_bytes()).hexdigest())
            self.assertEqual(event["audio_metadata"]["sample_rate"], 8000)
            self.assertEqual(event["audio_metadata"]["channels"], 1)
            self.assertEqual(event["audio_metadata"]["duration_seconds"], 0.25)
            self.assertIn("No claim is made that this file was placed on a specific Ableton track.", event["notes"])

    def test_observe_existing_files_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            sample_path = root / "loop.WAV"
            evidence_path = root / "evidence" / "sample_import_events.jsonl"
            _write_test_wav(sample_path)

            events = observe_existing_files(root, evidence_path)

            self.assertEqual(len(events), 1)
            lines = evidence_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["file_name"], "loop.WAV")

    def test_audio_file_detection_is_extension_based(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            wav_path = root / "sample.wav"
            txt_path = root / "notes.txt"
            wav_path.write_bytes(b"not a valid wav")
            txt_path.write_text("not audio", encoding="utf-8")

            self.assertTrue(is_audio_file(wav_path))
            self.assertFalse(is_audio_file(txt_path))


def _write_test_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(8000)
        audio_file.writeframes(b"\x00\x00" * 2000)


if __name__ == "__main__":
    unittest.main()
