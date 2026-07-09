from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from daemon.forgery_analysis.analyzer import HashChainAnalyzer

log = logging.getLogger(__name__)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str


@dataclass
class VerificationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def error(self, code: str, message: str) -> None:
        self.findings.append(Finding(Severity.ERROR, code, message))

    def warn(self, code: str, message: str) -> None:
        self.findings.append(Finding(Severity.WARNING, code, message))

    def info(self, code: str, message: str) -> None:
        self.findings.append(Finding(Severity.INFO, code, message))

    def error_messages(self) -> list[str]:
        return [f.message for f in self.errors]


def verify_manifest(manifest_path: Path) -> VerificationResult:
    result = VerificationResult()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        result.error("read_failed", f"Cannot read manifest: {e}")
        return result

    if "apw_version" not in data:
        result.error("missing_version", "Missing apw_version field")
    if "c2pa_mapping" not in data:
        result.error("missing_c2pa", "Missing c2pa_mapping field")
    if "apw:unobserved" not in data:
        result.error("missing_unobserved", "Missing apw:unobserved field (honesty model violation)")

    export = data.get("export")
    if export is None:
        result.error("no_export", "No export evidence in manifest")
    else:
        if not export.get("sha256"):
            result.error("export_no_hash", "Export missing sha256 hash")
        if not export.get("file_name"):
            result.error("export_no_name", "Export missing file_name")

    stems = data.get("observed_stems", [])
    if not stems:
        result.error("no_stems", "No observed stems in manifest (no audio stream evidence)")
    for i, stem in enumerate(stems):
        if not stem.get("hash_chain_root"):
            result.error("stem_no_root", f"Stem {i} missing hash_chain_root")
        if stem.get("hash_chain_length", 0) == 0:
            result.error("stem_empty_chain", f"Stem {i} has zero-length hash chain")

    assertions = data.get("c2pa_mapping", {}).get("assertions", [])
    labels = [a.get("label") for a in assertions]
    if "apw.unobserved" not in labels:
        result.error("c2pa_no_unobserved", "C2PA assertions missing apw.unobserved declaration")

    if "evidence_binding" not in data:
        result.warn("no_evidence_binding", "No evidence_binding (cannot trace manifest to evidence files)")
    else:
        binding = data["evidence_binding"]
        if not binding.get("evidence_file_hashes"):
            result.warn("empty_evidence_hashes", "Evidence binding has no file hashes")
        if binding.get("chain_length", 0) == 0:
            result.warn("binding_no_chain", "Evidence binding reports zero chain length")

    sig = data.get("manifest_signature")
    if sig is None:
        result.warn("unsigned", "Manifest is unsigned (no manifest_signature)")
    elif sig.get("signed_content_hash"):
        manifest_copy = {k: v for k, v in data.items() if k != "manifest_signature"}
        recomputed = hashlib.sha256(
            json.dumps(manifest_copy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if recomputed != sig["signed_content_hash"]:
            result.error("tampered", "Manifest content hash mismatch (manifest may have been tampered with)")
        else:
            result.info("signature_valid", "Manifest content hash verified")

    if "session_facts" in data:
        facts = data["session_facts"]
        track_count = len(facts.get("tracks", []))
        result.info("session_facts", f"Session facts present: {track_count} tracks, BPM {facts.get('bpm')}")
    else:
        result.warn("no_session_facts", "No session_facts (no .als project data)")

    return result


def verify_hash_chain(evidence_path: Path) -> VerificationResult:
    result = VerificationResult()
    analyzer = HashChainAnalyzer()

    try:
        lines = evidence_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        result.error("read_failed", f"Cannot read evidence: {e}")
        return result

    count = 0
    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            result.error("malformed_json", f"Malformed JSON at line {line_num}")
            continue
        if event.get("event_type") == "buffer_hash":
            analyzer.ingest_buffer_hash(event)
            count += 1

    if count == 0:
        result.error("no_hashes", "No buffer_hash events found in evidence file")
        return result

    report = analyzer.analyze()
    for flag in report.flags:
        if flag.severity >= 0.8:
            result.error(flag.name, f"{flag.description} ({flag.evidence})")
        else:
            result.warn(flag.name, f"{flag.description} ({flag.evidence})")

    if not report.flags:
        result.info("chain_intact", f"Hash chain verified: {count} windows, no breaks")

    return result


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Verify audio provenance manifest and hash chain integrity.")
    parser.add_argument("target", type=Path, help="Path to manifest JSON or evidence JSONL file.")
    args = parser.parse_args(argv or [])

    path = args.target
    if not path.exists():
        log.error("File not found: %s", path)
        return 1

    if path.suffix == ".json":
        log.info("Verifying manifest: %s", path)
        result = verify_manifest(path)
    elif path.suffix == ".jsonl":
        log.info("Verifying hash chain: %s", path)
        result = verify_hash_chain(path)
    else:
        log.info("Attempting both manifest and hash chain verification")
        result = verify_manifest(path)
        chain_result = verify_hash_chain(path)
        result.findings.extend(chain_result.findings)

    for f in result.findings:
        if f.severity == Severity.ERROR:
            log.error("FAIL: [%s] %s", f.code, f.message)
        elif f.severity == Severity.WARNING:
            log.warning("WARN: [%s] %s", f.code, f.message)
        else:
            log.info("OK:   [%s] %s", f.code, f.message)

    if result.passed:
        log.info("PASS: %d checks, %d warnings", len(result.findings), len(result.warnings))
        return 0
    else:
        log.error("FAIL: %d errors, %d warnings", len(result.errors), len(result.warnings))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
