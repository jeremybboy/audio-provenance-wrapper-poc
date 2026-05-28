from __future__ import annotations

import argparse
import json
import logging
import socket
import threading
import time
from pathlib import Path

from daemon.correlation_engine.engine import CorrelationEngine, LayerEvent
from daemon.evidence_receiver.receiver import EvidenceReceiver
from daemon.evidence_receiver.taxonomy import validate_event
from daemon.manifest_builder.builder import (
    ExportEvidence,
    IngredientEvidence,
    ManifestBuilder,
    StemEvidence,
)
from daemon.sample_watcher.watcher import SampleWatcher

log = logging.getLogger(__name__)

DEFAULT_UDP_PORT = 9876
DEFAULT_EVIDENCE_DIR = Path("evidence")
DEFAULT_SAMPLE_DIR = Path("~/Music/ProvenanceSamples")
DEFAULT_MANIFEST_DIR = Path("manifests")


class Daemon:
    """Unified daemon that orchestrates all observation layers."""

    def __init__(
        self,
        udp_port: int = DEFAULT_UDP_PORT,
        evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
        sample_dir: Path = DEFAULT_SAMPLE_DIR,
        project_path: Path | None = None,
        export_dir: Path | None = None,
        manifest_dir: Path = DEFAULT_MANIFEST_DIR,
    ) -> None:
        self.evidence_dir = evidence_dir.expanduser()
        self.manifest_dir = manifest_dir.expanduser()
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        self.receiver = EvidenceReceiver(
            host="127.0.0.1",
            port=udp_port,
            evidence_path=self.evidence_dir / "plugin_events.jsonl",
        )

        self.correlation = CorrelationEngine(
            window_ms=2000,
            evidence_path=self.evidence_dir / "composite_events.jsonl",
        )

        self.sample_watcher = SampleWatcher(
            watch_dir=sample_dir,
            evidence_path=self.evidence_dir / "sample_import_events.jsonl",
            poll_interval_seconds=2.0,
        )

        self.project_path = project_path
        self.export_dir = export_dir.expanduser() if export_dir else None
        self._export_seen: set[str] = set()
        self._session_events: list[dict[str, object]] = []
        self._stop = threading.Event()

    def run(self) -> None:
        threads: list[threading.Thread] = [
            threading.Thread(target=self._run_udp_receiver, name="udp-receiver", daemon=True),
            threading.Thread(target=self._run_sample_watcher, name="sample-watcher", daemon=True),
        ]

        if self.project_path and self.project_path.exists():
            threads.append(
                threading.Thread(target=self._run_project_watcher, name="project-watcher", daemon=True)
            )

        if self.export_dir:
            threads.append(
                threading.Thread(target=self._run_export_watcher, name="export-watcher", daemon=True)
            )

        log.info("Daemon starting with %d threads", len(threads))
        for t in threads:
            t.start()

        try:
            while not self._stop.is_set():
                self._stop.wait(1.0)
        except KeyboardInterrupt:
            log.info("Shutting down")
            self._stop.set()

    def _run_udp_receiver(self) -> None:
        log.info("UDP receiver on port %d", self.receiver.port)
        self.receiver.sock.settimeout(1.0)

        while not self._stop.is_set():
            try:
                data, _addr = self.receiver.sock.recvfrom(4096)
            except socket.timeout:
                continue

            event = self.receiver.process_packet(data)
            if event is None:
                continue

            self._session_events.append(event)

            layer_event = LayerEvent(
                layer="audio_buffer",
                event_type=str(event.get("event_type", "")),
                timestamp_ms=int(event.get("timestamp_ms", 0)),
                data=event,
            )
            composites = self.correlation.ingest(layer_event)
            for c in composites:
                log.info("Composite edit: %s (%.2f)", c.edit_type, c.confidence)

    def _run_sample_watcher(self) -> None:
        self.sample_watcher.mark_existing_seen()
        log.info("Sample watcher on %s", self.sample_watcher.watch_dir)

        while not self._stop.is_set():
            events = self.sample_watcher.scan_once()
            for event in events:
                log.info("Sample detected: %s", event.get("file_name"))
                self._session_events.append(event)

                layer_event = LayerEvent(
                    layer="sample_watcher",
                    event_type="sample_file_observed",
                    timestamp_ms=int(time.time() * 1000),
                    data=event,
                )
                self.correlation.ingest(layer_event)

            time.sleep(self.sample_watcher.poll_interval_seconds)

    def _run_project_watcher(self) -> None:
        from daemon.project_differ.differ import ProjectWatcher, extract_snapshot, compute_diff

        log.info("Project watcher on %s", self.project_path)
        prev_snapshot = None
        prev_mtime_ns = 0

        while not self._stop.is_set():
            try:
                stat = self.project_path.stat()
            except OSError:
                time.sleep(2.0)
                continue

            if stat.st_mtime_ns != prev_mtime_ns:
                prev_mtime_ns = stat.st_mtime_ns
                try:
                    snapshot = extract_snapshot(self.project_path)
                except Exception:
                    log.exception("Failed to parse %s", self.project_path)
                    time.sleep(2.0)
                    continue

                if prev_snapshot is not None:
                    diff = compute_diff(prev_snapshot, snapshot)
                    if diff.has_changes():
                        diff_event = {
                            "event_type": "project_diff",
                            "proof_level": "directly_observed",
                            "timestamp_ms": int(time.time() * 1000),
                            "clips_added": diff.clips_added,
                            "clips_removed": diff.clips_removed,
                            "clips_modified": diff.clips_modified,
                            "tracks_added": diff.tracks_added,
                            "tracks_removed": diff.tracks_removed,
                            "devices_changed": diff.devices_changed,
                            "samples_added": sorted(diff.samples_added),
                            "samples_removed": sorted(diff.samples_removed),
                            "midi_notes_delta": diff.midi_notes_delta,
                            "automation_points_delta": diff.automation_points_delta,
                            "bpm_changed": diff.bpm_changed,
                        }
                        self._write_evidence("project_diff_events.jsonl", diff_event)
                        self._session_events.append(diff_event)

                        layer_event = LayerEvent(
                            layer="project_differ",
                            event_type="project_diff",
                            timestamp_ms=int(time.time() * 1000),
                            data=diff_event,
                        )
                        self.correlation.ingest(layer_event)
                        log.info(
                            "Project diff: +%d/-%d/~%d clips",
                            diff.clips_added, diff.clips_removed, diff.clips_modified,
                        )

                prev_snapshot = snapshot

            time.sleep(2.0)

    def _run_export_watcher(self) -> None:
        log.info("Export watcher on %s", self.export_dir)
        AUDIO_EXTENSIONS = {".wav", ".aiff", ".aif"}

        for existing in self.export_dir.iterdir():
            if existing.is_file() and existing.suffix.lower() in AUDIO_EXTENSIONS:
                self._export_seen.add(str(existing.resolve()))

        while not self._stop.is_set():
            try:
                for path in self.export_dir.iterdir():
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in AUDIO_EXTENSIONS:
                        continue

                    resolved = str(path.resolve())
                    if resolved in self._export_seen:
                        continue

                    time.sleep(1.0)
                    if not path.exists():
                        continue

                    self._export_seen.add(resolved)
                    log.info("Export detected: %s", path.name)
                    self._generate_manifest(path)
            except OSError:
                pass

            time.sleep(2.0)

    def _generate_manifest(self, export_path: Path) -> None:
        import hashlib

        digest = hashlib.sha256()
        with export_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)

        stat = export_path.stat()
        builder = ManifestBuilder(
            session_id=f"session-{int(time.time())}",
        )
        builder.set_export(ExportEvidence(
            file_path=str(export_path),
            file_name=export_path.name,
            sha256=digest.hexdigest(),
            format=export_path.suffix.lower().lstrip("."),
            file_size_bytes=stat.st_size,
            duration_seconds=None,
            exported_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ))

        for event in self._session_events:
            et = event.get("event_type")
            if et == "sample_file_observed":
                builder.add_ingredient(IngredientEvidence(
                    file_name=str(event.get("file_name", "")),
                    sha256=str(event.get("sha256", "")),
                    proof_level=str(event.get("proof_level", "directly_observed")),
                    correlation_confidence=None,
                    audio_fingerprint=event.get("audio_fingerprint"),
                ))
            elif et == "composite_edit":
                builder.add_composite_edit(event)

        manifest_path = self.manifest_dir / f"{export_path.stem}_manifest.json"
        builder.write_json(manifest_path)
        log.info("Manifest written: %s", manifest_path)

    def _write_evidence(self, filename: str, event: dict[str, object]) -> None:
        path = self.evidence_dir / filename
        with path.open("a", encoding="utf-8") as f:
            json.dump(event, f, separators=(",", ":"))
            f.write("\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audio provenance daemon: receives plugin events, watches files, generates manifests.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_UDP_PORT, help="UDP port for plugin events.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR, help="Evidence output directory.")
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR, help="Sample watch directory.")
    parser.add_argument("--project", type=Path, default=None, help="Ableton .als project file to watch.")
    parser.add_argument("--export-dir", type=Path, default=None, help="Export directory to watch for WAV/AIFF.")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR, help="Manifest output directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args(argv or [])
    daemon = Daemon(
        udp_port=args.port,
        evidence_dir=args.evidence_dir,
        sample_dir=args.sample_dir,
        project_path=args.project,
        export_dir=args.export_dir,
        manifest_dir=args.manifest_dir,
    )
    daemon.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
