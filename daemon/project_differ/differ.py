from __future__ import annotations

import argparse
import gzip
import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from daemon.common import sha256_file

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackInfo:
    """Rich per-track metadata extracted from the .als XML."""

    name: str
    track_type: str
    devices: tuple[str, ...]
    sample_paths: tuple[str, ...]
    clip_count: int
    automation_point_count: int
    midi_note_count: int
    group_id: str
    routing_input: str
    routing_output: str


@dataclass(frozen=True)
class ProjectSnapshot:
    """Structural fingerprint of an Ableton .als project at a point in time."""

    file_hash: str
    file_size_bytes: int
    track_count: int
    track_names: tuple[str, ...]
    tracks: tuple[TrackInfo, ...]
    clip_count: int
    clip_hashes: frozenset[str]
    device_chain_hashes: frozenset[str]
    automation_point_count: int
    midi_note_count: int
    sample_refs: frozenset[str]
    transport_bpm: float
    transport_loop_on: bool
    transport_loop_range: tuple[float, float]
    locator_count: int


@dataclass
class ProjectDiff:
    """Structural diff between two project snapshots."""

    timestamp_ms: int
    previous_file_hash: str
    current_file_hash: str
    tracks_added: list[str] = field(default_factory=list)
    tracks_removed: list[str] = field(default_factory=list)
    clips_added: int = 0
    clips_removed: int = 0
    clips_modified: int = 0
    devices_changed: list[str] = field(default_factory=list)
    automation_points_delta: int = 0
    midi_notes_delta: int = 0
    samples_added: frozenset[str] = field(default_factory=frozenset)
    samples_removed: frozenset[str] = field(default_factory=frozenset)
    bpm_changed: bool = False
    loop_changed: bool = False
    locators_delta: int = 0

    def has_changes(self) -> bool:
        return (
            bool(self.tracks_added)
            or bool(self.tracks_removed)
            or self.clips_added > 0
            or self.clips_removed > 0
            or self.clips_modified > 0
            or bool(self.devices_changed)
            or self.automation_points_delta != 0
            or self.midi_notes_delta != 0
            or bool(self.samples_added)
            or bool(self.samples_removed)
            or self.bpm_changed
            or self.loop_changed
            or self.locators_delta != 0
        )


def parse_als(path: Path) -> ET.Element:
    """Decompress and parse an Ableton .als file.

    Stub: returns the parsed XML root element. Raises on invalid files.
    """
    with gzip.open(path, "rb") as f:
        return ET.parse(f).getroot()


def extract_snapshot(path: Path) -> ProjectSnapshot:
    """Extract a structural snapshot from an .als file.

    Stub: the XML traversal paths below reflect the known Ableton .als
    structure but are not exhaustively tested across versions.
    """
    root = parse_als(path)
    live_set = root.find("LiveSet")
    if live_set is None:
        raise ValueError(f"No LiveSet element in {path}")

    tracks_el = live_set.find("Tracks")
    track_names: list[str] = []
    clip_hashes: set[str] = set()
    device_hashes: set[str] = set()
    sample_refs: set[str] = set()
    clip_count = 0
    automation_count = 0
    midi_note_count = 0

    track_infos: list[TrackInfo] = []

    if tracks_el is not None:
        for track in tracks_el:
            name_el = track.find("Name")
            name_val = ""
            if name_el is not None:
                eff = name_el.find("EffectiveName")
                if eff is not None:
                    name_val = eff.get("Value", "")
            track_names.append(name_val)

            track_type = track.tag
            track_clips = 0
            track_auto = 0
            track_midi = 0
            track_devices: list[str] = []
            track_samples: list[str] = []

            for clip_slot in track.iter("ClipSlot"):
                clip_count += 1
                track_clips += 1
                clip_hashes.add(hashlib.sha256(ET.tostring(clip_slot)).hexdigest()[:16])

            for device_chain in track.iter("DeviceChain"):
                device_hashes.add(hashlib.sha256(ET.tostring(device_chain)).hexdigest()[:16])
                devices_el = device_chain.find(".//Devices")
                if devices_el is not None:
                    for device in devices_el:
                        dev_name = device.tag
                        user_name_el = device.find(".//UserName")
                        if user_name_el is not None and user_name_el.get("Value"):
                            dev_name = user_name_el.get("Value", dev_name)
                        track_devices.append(dev_name)

            for file_ref in track.iter("FileRef"):
                rel = file_ref.find("RelativePath")
                if rel is not None:
                    val = rel.get("Value", "")
                    if val:
                        sample_refs.add(val)
                        track_samples.append(val)
                abs_el = file_ref.find("Path")
                if abs_el is not None:
                    val = abs_el.get("Value", "")
                    if val:
                        sample_refs.add(val)
                        if val not in track_samples:
                            track_samples.append(val)

            for notes_el in track.iter("Notes"):
                for key_track in notes_el.iter("KeyTrack"):
                    c = sum(1 for _ in key_track.iter("MidiNoteEvent"))
                    midi_note_count += c
                    track_midi += c

            track_auto = sum(1 for _ in track.iter("AutomationPoint"))
            automation_count += track_auto

            group_id = ""
            group_el = track.find("TrackGroupId")
            if group_el is not None:
                group_id = group_el.get("Value", "")

            routing_in = ""
            routing_out = ""
            input_routing = track.find(".//AudioInputRouting/Target")
            if input_routing is not None:
                routing_in = input_routing.get("Value", "")
            output_routing = track.find(".//AudioOutputRouting/Target")
            if output_routing is not None:
                routing_out = output_routing.get("Value", "")

            track_infos.append(TrackInfo(
                name=name_val,
                track_type=track_type,
                devices=tuple(track_devices),
                sample_paths=tuple(track_samples),
                clip_count=track_clips,
                automation_point_count=track_auto,
                midi_note_count=track_midi,
                group_id=group_id,
                routing_input=routing_in,
                routing_output=routing_out,
            ))

    transport = live_set.find("Transport")
    bpm = 120.0
    loop_on = False
    loop_start = 0.0
    loop_length = 0.0
    if transport is not None:
        tempo_el = transport.find(".//Tempo/Manual")
        if tempo_el is not None:
            bpm = float(tempo_el.get("Value", "120"))
        loop_on_el = transport.find("LoopOn")
        if loop_on_el is not None:
            loop_on = loop_on_el.get("Value", "false") == "true"
        loop_start_el = transport.find("LoopStart")
        if loop_start_el is not None:
            loop_start = float(loop_start_el.get("Value", "0"))
        loop_len_el = transport.find("LoopLength")
        if loop_len_el is not None:
            loop_length = float(loop_len_el.get("Value", "0"))

    locator_count = sum(1 for _ in live_set.iter("Locator"))

    stat = path.stat()

    return ProjectSnapshot(
        file_hash=sha256_file(path),
        file_size_bytes=stat.st_size,
        track_count=len(track_names),
        track_names=tuple(track_names),
        tracks=tuple(track_infos),
        clip_count=clip_count,
        clip_hashes=frozenset(clip_hashes),
        device_chain_hashes=frozenset(device_hashes),
        automation_point_count=automation_count,
        midi_note_count=midi_note_count,
        sample_refs=frozenset(sample_refs),
        transport_bpm=bpm,
        transport_loop_on=loop_on,
        transport_loop_range=(loop_start, loop_length),
        locator_count=locator_count,
    )


def compute_diff(previous: ProjectSnapshot, current: ProjectSnapshot) -> ProjectDiff:
    prev_names = set(previous.track_names)
    curr_names = set(current.track_names)

    new_clips = current.clip_hashes - previous.clip_hashes
    removed_clips = previous.clip_hashes - current.clip_hashes
    common_count = len(current.clip_hashes & previous.clip_hashes)
    modified_clips = abs(current.clip_count - previous.clip_count) - len(new_clips) - len(removed_clips)
    if modified_clips < 0:
        modified_clips = 0

    prev_devices = previous.device_chain_hashes
    curr_devices = current.device_chain_hashes
    devices_changed: list[str] = []
    if prev_devices != curr_devices:
        for i, name in enumerate(current.track_names):
            devices_changed.append(name)

    return ProjectDiff(
        timestamp_ms=int(time.time() * 1000),
        previous_file_hash=previous.file_hash,
        current_file_hash=current.file_hash,
        tracks_added=sorted(curr_names - prev_names),
        tracks_removed=sorted(prev_names - curr_names),
        clips_added=len(new_clips),
        clips_removed=len(removed_clips),
        clips_modified=modified_clips,
        devices_changed=devices_changed if prev_devices != curr_devices else [],
        automation_points_delta=current.automation_point_count - previous.automation_point_count,
        midi_notes_delta=current.midi_note_count - previous.midi_note_count,
        samples_added=current.sample_refs - previous.sample_refs,
        samples_removed=previous.sample_refs - current.sample_refs,
        bpm_changed=current.transport_bpm != previous.transport_bpm,
        loop_changed=(current.transport_loop_on != previous.transport_loop_on
                      or current.transport_loop_range != previous.transport_loop_range),
        locators_delta=current.locator_count - previous.locator_count,
    )


class ProjectWatcher:
    """Watches an Ableton .als file for saves and emits structural diffs.

    Stub: the polling loop is functional but the extract_snapshot parser
    needs validation against real .als files across Ableton versions.
    """

    def __init__(
        self,
        project_path: Path,
        evidence_path: Path = Path("evidence/project_diff_events.jsonl"),
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.project_path = project_path.expanduser()
        self.evidence_path = evidence_path.expanduser()
        self.poll_interval_seconds = poll_interval_seconds
        self._previous_snapshot: ProjectSnapshot | None = None
        self._previous_mtime_ns: int = 0

    def run_forever(self) -> None:
        """Poll the project file and emit diffs on each save.

        Stub: actual implementation will also write events to the JSONL
        evidence file, matching the pattern in evidence_receiver.
        """
        log.info("Watching %s for saves; writing %s", self.project_path, self.evidence_path)

        while True:
            try:
                stat = self.project_path.stat()
            except OSError:
                time.sleep(self.poll_interval_seconds)
                continue

            if stat.st_mtime_ns != self._previous_mtime_ns:
                self._previous_mtime_ns = stat.st_mtime_ns
                try:
                    snapshot = extract_snapshot(self.project_path)
                except Exception:
                    log.exception("Failed to parse %s", self.project_path)
                    time.sleep(self.poll_interval_seconds)
                    continue

                if self._previous_snapshot is not None:
                    diff = compute_diff(self._previous_snapshot, snapshot)
                    if diff.has_changes():
                        log.info(
                            "Project diff: +%d/-%d/%d~ clips, %d samples added",
                            diff.clips_added,
                            diff.clips_removed,
                            diff.clips_modified,
                            len(diff.samples_added),
                        )

                self._previous_snapshot = snapshot

            time.sleep(self.poll_interval_seconds)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch an Ableton .als project file and emit structural diffs.",
    )
    parser.add_argument("project_path", type=Path, help="Path to the .als file.")
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("evidence/project_diff_events.jsonl"),
        help="JSONL output path.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between file checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv or [])
    watcher = ProjectWatcher(
        project_path=args.project_path,
        evidence_path=args.evidence_file,
        poll_interval_seconds=args.poll_interval,
    )
    try:
        watcher.run_forever()
    except KeyboardInterrupt:
        return 0
    return 0
