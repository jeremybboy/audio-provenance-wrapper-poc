import unittest

from daemon.project_differ.differ import (
    ProjectDiff,
    ProjectSnapshot,
    compute_diff,
)


def _make_snapshot(**overrides) -> ProjectSnapshot:
    defaults = dict(
        file_hash="aaa",
        file_size_bytes=1000,
        track_count=2,
        track_names=("Track 1", "Track 2"),
        clip_count=4,
        clip_hashes=frozenset({"c1", "c2", "c3", "c4"}),
        device_chain_hashes=frozenset({"d1", "d2"}),
        automation_point_count=10,
        midi_note_count=50,
        sample_refs=frozenset({"sample_a.wav"}),
        transport_bpm=120.0,
        transport_loop_on=False,
        transport_loop_range=(0.0, 0.0),
        locator_count=2,
    )
    defaults.update(overrides)
    return ProjectSnapshot(**defaults)


class ComputeDiffTests(unittest.TestCase):
    def test_no_changes(self):
        snap = _make_snapshot()
        diff = compute_diff(snap, snap)
        self.assertFalse(diff.has_changes())

    def test_tracks_added(self):
        prev = _make_snapshot(track_names=("Track 1",))
        curr = _make_snapshot(track_names=("Track 1", "Track 2"))
        diff = compute_diff(prev, curr)
        self.assertIn("Track 2", diff.tracks_added)

    def test_tracks_removed(self):
        prev = _make_snapshot(track_names=("Track 1", "Track 2"))
        curr = _make_snapshot(track_names=("Track 1",))
        diff = compute_diff(prev, curr)
        self.assertIn("Track 2", diff.tracks_removed)

    def test_clips_added(self):
        prev = _make_snapshot(clip_hashes=frozenset({"c1", "c2"}))
        curr = _make_snapshot(clip_hashes=frozenset({"c1", "c2", "c3"}))
        diff = compute_diff(prev, curr)
        self.assertEqual(diff.clips_added, 1)
        self.assertEqual(diff.clips_removed, 0)

    def test_clips_removed(self):
        prev = _make_snapshot(clip_hashes=frozenset({"c1", "c2", "c3"}))
        curr = _make_snapshot(clip_hashes=frozenset({"c1", "c2"}))
        diff = compute_diff(prev, curr)
        self.assertEqual(diff.clips_removed, 1)

    def test_samples_added(self):
        prev = _make_snapshot(sample_refs=frozenset({"a.wav"}))
        curr = _make_snapshot(sample_refs=frozenset({"a.wav", "b.wav"}))
        diff = compute_diff(prev, curr)
        self.assertIn("b.wav", diff.samples_added)
        self.assertTrue(diff.has_changes())

    def test_bpm_changed(self):
        prev = _make_snapshot(transport_bpm=120.0)
        curr = _make_snapshot(transport_bpm=140.0)
        diff = compute_diff(prev, curr)
        self.assertTrue(diff.bpm_changed)

    def test_midi_notes_delta(self):
        prev = _make_snapshot(midi_note_count=50)
        curr = _make_snapshot(midi_note_count=75)
        diff = compute_diff(prev, curr)
        self.assertEqual(diff.midi_notes_delta, 25)

    def test_devices_changed(self):
        prev = _make_snapshot(device_chain_hashes=frozenset({"d1"}))
        curr = _make_snapshot(device_chain_hashes=frozenset({"d2"}))
        diff = compute_diff(prev, curr)
        self.assertTrue(len(diff.devices_changed) > 0)


class ProjectDiffHasChangesTests(unittest.TestCase):
    def test_empty_diff(self):
        diff = ProjectDiff(timestamp_ms=0, previous_file_hash="a", current_file_hash="a")
        self.assertFalse(diff.has_changes())

    def test_any_nonzero_field_means_changes(self):
        diff = ProjectDiff(timestamp_ms=0, previous_file_hash="a", current_file_hash="b", clips_added=1)
        self.assertTrue(diff.has_changes())


if __name__ == "__main__":
    unittest.main()
