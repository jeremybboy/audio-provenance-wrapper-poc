from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from daemon.forgery_analysis.analyzer import HashChainAnalyzer

log = logging.getLogger(__name__)


def verify_manifest(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [f"Cannot read manifest: {e}"]

    if "apw_version" not in data:
        errors.append("Missing apw_version field")
    if "c2pa_mapping" not in data:
        errors.append("Missing c2pa_mapping field")
    if "apw:unobserved" not in data:
        errors.append("Missing apw:unobserved field (honesty model violation)")

    export = data.get("export")
    if export is None:
        errors.append("No export evidence in manifest")
    else:
        if not export.get("sha256"):
            errors.append("Export missing sha256 hash")
        if not export.get("file_name"):
            errors.append("Export missing file_name")

    stems = data.get("observed_stems", [])
    if not stems:
        errors.append("No observed stems in manifest (no audio stream evidence)")
    for i, stem in enumerate(stems):
        if not stem.get("hash_chain_root"):
            errors.append(f"Stem {i} missing hash_chain_root")
        if stem.get("hash_chain_length", 0) == 0:
            errors.append(f"Stem {i} has zero-length hash chain")

    assertions = data.get("c2pa_mapping", {}).get("assertions", [])
    labels = [a.get("label") for a in assertions]
    if "apw.unobserved" not in labels:
        errors.append("C2PA assertions missing apw.unobserved declaration")

    if "evidence_binding" not in data:
        errors.append("No evidence_binding (cannot trace manifest to evidence files)")

    sig = data.get("manifest_signature")
    if sig is None:
        errors.append("Manifest is unsigned (no manifest_signature)")
    elif sig.get("signed_content_hash"):
        import hashlib
        manifest_copy = {k: v for k, v in data.items() if k != "manifest_signature"}
        recomputed = hashlib.sha256(
            json.dumps(manifest_copy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if recomputed != sig["signed_content_hash"]:
            errors.append("Manifest content hash mismatch (manifest may have been tampered with)")

    return errors


def verify_hash_chain(evidence_path: Path) -> list[str]:
    errors: list[str] = []
    analyzer = HashChainAnalyzer()

    try:
        lines = evidence_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return [f"Cannot read evidence: {e}"]

    count = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"Malformed JSON at line {count + 1}")
            continue
        if event.get("event_type") == "buffer_hash":
            analyzer.ingest_buffer_hash(event)
            count += 1

    if count == 0:
        return ["No buffer_hash events found in evidence file"]

    report = analyzer.analyze()
    for flag in report.flags:
        errors.append(f"{flag.name}: {flag.description} ({flag.evidence})")

    return errors


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
        errors = verify_manifest(path)
    elif path.suffix == ".jsonl":
        log.info("Verifying hash chain: %s", path)
        errors = verify_hash_chain(path)
    else:
        log.info("Attempting both manifest and hash chain verification")
        errors = verify_manifest(path) + verify_hash_chain(path)

    if errors:
        for e in errors:
            log.error("FAIL: %s", e)
        return 1

    log.info("PASS: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
