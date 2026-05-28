from __future__ import annotations

import argparse
import hashlib
import json
import logging
import socket
import threading
import time
from pathlib import Path

from daemon.correlation_engine.engine import CorrelationEngine, LayerEvent
from daemon.evidence_receiver.receiver import EvidenceReceiver
from daemon.hardware_attestation.provider import SoftwareProvider, detect_provider
from daemon.manifest_builder.builder import (
    ExportEvidence,
    IngredientEvidence,
    ManifestBuilder,
    StemEvidence,
)
from daemon.sample_watcher.watcher import SampleWatcher

log = logging.getLogger(__name__)

_LAYER_MAP: dict[str, str] = {
    "buffer_hash": "audio_buffer",
    "audio_transition": "audio_buffer",
    "spectral_shift": "audio_buffer",
    "spectral_profile_change": "audio_buffer",
    "transport_change": "transport",
    "midi_event": "midi",
    "parameter_change": "midi",
    "session_config_change": "session",
}


def _event_type_to_layer(event_type: str) -> str:
    return _LAYER_MAP.get(event_type, "audio_buffer")


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
        self._session_lock = threading.Lock()
        self._session_events: list[dict[str, object]] = []
        self._active_layers: set[str] = {"audio_buffer", "sample_watcher"}
        self._latest_project_snapshot = None
        self._stop = threading.Event()

        try:
            self._hw_provider = detect_provider()
        except Exception:
            self._hw_provider = SoftwareProvider(
                key_path=Path("~/.apw/device_key.bin")
            )

    def _append_event(self, event: dict[str, object]) -> None:
        with self._session_lock:
            self._session_events.append(event)

    def _correlate(self, layer_event: LayerEvent) -> None:
        try:
            composites = self.correlation.ingest(layer_event)
        except Exception:
            log.exception("Correlation engine error")
            return
        for c in composites:
            log.info("Composite edit: %s (%.2f)", c.edit_type, c.confidence)
            self._append_event(c.to_event_dict())

    def run(self) -> None:
        threads: list[threading.Thread] = [
            threading.Thread(target=self._run_udp_receiver, name="udp-receiver", daemon=True),
            threading.Thread(target=self._run_sample_watcher, name="sample-watcher", daemon=True),
        ]

        if self.project_path and self.project_path.exists():
            self._active_layers.add("project_differ")
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
                data, _addr = self.receiver.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                log.exception("UDP socket error")
                continue

            event = self.receiver.process_packet(data)
            if event is None:
                continue

            self._append_event(event)

            et = str(event.get("event_type", ""))
            layer = _event_type_to_layer(et)
            layer_event = LayerEvent(
                layer=layer,
                event_type=et,
                timestamp_ms=int(event.get("timestamp_ms", 0)),
                data=event,
            )
            self._correlate(layer_event)

    def _run_sample_watcher(self) -> None:
        self.sample_watcher.mark_existing_seen()
        log.info("Sample watcher on %s", self.sample_watcher.watch_dir)

        while not self._stop.is_set():
            try:
                events = self.sample_watcher.scan_once()
            except Exception:
                log.exception("Sample watcher error")
                time.sleep(self.sample_watcher.poll_interval_seconds)
                continue

            for event in events:
                log.info("Sample detected: %s", event.get("file_name"))
                self._append_event(event)

                layer_event = LayerEvent(
                    layer="sample_watcher",
                    event_type="sample_file_observed",
                    timestamp_ms=int(time.time() * 1000),
                    data=event,
                )
                self._correlate(layer_event)

            time.sleep(self.sample_watcher.poll_interval_seconds)

    def _run_project_watcher(self) -> None:
        from daemon.project_differ.differ import extract_snapshot, compute_diff

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
                        diff_event: dict[str, object] = {
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
                        self._append_event(diff_event)

                        layer_event = LayerEvent(
                            layer="project_differ",
                            event_type="project_diff",
                            timestamp_ms=int(time.time() * 1000),
                            data=diff_event,
                        )
                        self._correlate(layer_event)
                        log.info(
                            "Project diff: +%d/-%d/~%d clips",
                            diff.clips_added, diff.clips_removed, diff.clips_modified,
                        )

                prev_snapshot = snapshot
                self._latest_project_snapshot = snapshot

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

                    if not self._file_is_stable(path):
                        continue

                    self._export_seen.add(resolved)
                    log.info("Export detected: %s", path.name)
                    self._generate_manifest(path)
            except OSError:
                pass

            time.sleep(2.0)

    def _generate_manifest(self, export_path: Path) -> None:
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

        first_hash_ms = 0
        last_hash_ms = 0
        last_window_hash = ""
        chain_root = ""
        chain_length = 0
        stem_sr = 0
        stem_ch = 0

        with self._session_lock:
            events_snapshot = list(self._session_events)

        for event in events_snapshot:
            et = event.get("event_type")
            if et == "buffer_hash":
                chain_length += 1
                ts = int(event.get("timestamp_ms", 0))
                if chain_length == 1:
                    first_hash_ms = ts
                    chain_root = str(event.get("prev_hash", "genesis"))
                last_hash_ms = ts
                last_window_hash = str(event.get("window_hash", ""))
                stem_sr = int(event.get("sample_rate_hz", stem_sr))
                stem_ch = int(event.get("channel_count", stem_ch))
            elif et == "sample_file_observed":
                builder.add_ingredient(IngredientEvidence(
                    file_name=str(event.get("file_name", "")),
                    sha256=str(event.get("sha256", "")),
                    proof_level=str(event.get("proof_level", "directly_observed")),
                    correlation_confidence=None,
                    audio_fingerprint=event.get("audio_fingerprint"),
                ))
            elif et == "composite_edit":
                builder.add_composite_edit(event)

        if chain_length > 0:
            builder.add_stem(StemEvidence(
                stem_id="stem-1",
                hash_chain_root=chain_root,
                hash_chain_length=chain_length,
                first_observed_ms=first_hash_ms,
                last_observed_ms=last_hash_ms,
                sample_rate_hz=stem_sr,
                channel_count=stem_ch,
                source_category="unknown",
                proof_level="directly_observed",
            ))

        all_layers = {"audio_buffer", "transport", "midi", "session",
                      "sample_watcher", "project_differ", "input_capture",
                      "screen_observer"}
        missing_layers = sorted(all_layers - self._active_layers)
        builder.unobserved = list(builder.unobserved)
        for layer in missing_layers:
            builder.unobserved.append(f"layer_{layer}_not_active")

        evidence_hashes: dict[str, str] = {}
        for evidence_file in self.evidence_dir.glob("*.jsonl"):
            h = hashlib.sha256()
            h.update(evidence_file.read_bytes())
            evidence_hashes[evidence_file.name] = h.hexdigest()

        manifest = builder.build()

        snap = self._latest_project_snapshot
        if snap is not None:
            manifest["session_facts"] = {
                "bpm": snap.transport_bpm,
                "loop_on": snap.transport_loop_on,
                "track_count": snap.track_count,
                "clip_count": snap.clip_count,
                "sample_refs": sorted(snap.sample_refs),
                "tracks": [
                    {
                        "name": t.name,
                        "type": t.track_type,
                        "devices": list(t.devices),
                        "sample_paths": list(t.sample_paths),
                        "clip_count": t.clip_count,
                        "midi_note_count": t.midi_note_count,
                        "automation_point_count": t.automation_point_count,
                        "routing_input": t.routing_input,
                        "routing_output": t.routing_output,
                        "group_id": t.group_id,
                    }
                    for t in snap.tracks
                ],
            }
        manifest["evidence_binding"] = {
            "evidence_file_hashes": evidence_hashes,
            "last_window_hash": last_window_hash,
            "chain_length": chain_length,
        }

        try:
            identity = self._hw_provider.device_identity()
            manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            signature = self._hw_provider.sign(manifest_bytes)
            manifest["manifest_signature"] = {
                "algorithm": identity.algorithm,
                "device_id": identity.device_id,
                "public_key_hex": identity.public_key_hex,
                "signature_hex": signature.hex(),
                "signed_content_hash": hashlib.sha256(manifest_bytes).hexdigest(),
            }
        except Exception:
            log.warning("Could not sign manifest (hardware provider unavailable)")

        manifest_path = self.manifest_dir / f"{export_path.stem}_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        log.info("Manifest written: %s", manifest_path)

    @staticmethod
    def _file_is_stable(path: Path, checks: int = 3, interval: float = 0.5) -> bool:
        try:
            prev_size = path.stat().st_size
        except OSError:
            return False
        for _ in range(checks):
            time.sleep(interval)
            try:
                cur_size = path.stat().st_size
            except OSError:
                return False
            if cur_size != prev_size:
                return False
            prev_size = cur_size
        return prev_size > 0

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
