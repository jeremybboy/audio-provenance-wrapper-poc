from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from daemon.common import utc_timestamp

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StemEvidence:
    """Evidence for a single observed audio stem."""

    stem_id: str
    hash_chain_root: str
    hash_chain_length: int
    first_observed_ms: int
    last_observed_ms: int
    sample_rate_hz: int
    channel_count: int
    source_category: str
    proof_level: str


@dataclass(frozen=True)
class ExportEvidence:
    """Evidence for a final exported audio file."""

    file_path: str
    file_name: str
    sha256: str
    format: str
    file_size_bytes: int
    duration_seconds: float | None
    exported_at: str


@dataclass(frozen=True)
class IngredientEvidence:
    """Evidence for an observed sample ingredient."""

    file_name: str
    sha256: str
    proof_level: str
    correlation_confidence: float | None
    audio_fingerprint: dict[str, float | None] | None


@dataclass
class ManifestBuilder:
    """Builds a C2PA-compatible crJSON manifest from composite evidence.

    The manifest maps internal provenance evidence to C2PA assertion
    structures. This is the "fight card" manifest described in
    docs/MANIFEST_SCHEMA.md.

    C2PA mapping:
        stems         → c2pa.ingredient assertions (type: audio/*)
        export        → c2pa.asset assertion (the final output)
        edit_history  → c2pa.actions assertion (edit operations)
        hash_chain    → c2pa.hash assertion (content binding)
        ingredients   → c2pa.ingredient assertions (samples)
        hardware      → c2pa.claim_signature (device binding)
        time_anchors  → c2pa.timestamp assertions

    Proof levels are preserved as custom extensions:
        "apw:proof_level": "directly_observed" | "inferred" | etc.

    Unknown or unobserved data is explicitly represented:
        "apw:unobserved": ["hidden_plugin_state", "bypassed_routing", ...]
    """

    session_id: str = ""
    created_at: str = field(default_factory=utc_timestamp)
    stems: list[StemEvidence] = field(default_factory=list)
    export: ExportEvidence | None = None
    ingredients: list[IngredientEvidence] = field(default_factory=list)
    composite_edits: list[dict[str, object]] = field(default_factory=list)
    hardware_binding: dict[str, object] | None = None
    time_anchors: list[dict[str, object]] = field(default_factory=list)
    forgery_report: dict[str, object] | None = None
    unobserved: list[str] = field(default_factory=lambda: [
        "hidden_plugin_state",
        "internal_preset_logic",
        "bypassed_routing",
        "daw_internal_processing",
        "unverifiable_upstream_provenance",
    ])

    def add_stem(self, stem: StemEvidence) -> None:
        self.stems.append(stem)

    def set_export(self, export: ExportEvidence) -> None:
        self.export = export

    def add_ingredient(self, ingredient: IngredientEvidence) -> None:
        self.ingredients.append(ingredient)

    def add_composite_edit(self, edit: dict[str, object]) -> None:
        self.composite_edits.append(edit)

    def set_hardware_binding(self, binding: dict[str, object]) -> None:
        self.hardware_binding = binding

    def add_time_anchor(self, anchor: dict[str, object]) -> None:
        self.time_anchors.append(anchor)

    def set_forgery_report(self, report: dict[str, object]) -> None:
        self.forgery_report = report

    def build(self) -> dict[str, object]:
        """Build the complete crJSON manifest."""
        manifest: dict[str, object] = {
            "apw_version": "0.2.0",
            "schema": "audio-provenance-manifest-v0",
            "session_id": self.session_id,
            "created_at": self.created_at,
            "core_principle": "Never claim full DAW provenance.",
        }

        manifest["observed_stems"] = [
            {
                "stem_id": s.stem_id,
                "hash_chain_root": s.hash_chain_root,
                "hash_chain_length": s.hash_chain_length,
                "first_observed_ms": s.first_observed_ms,
                "last_observed_ms": s.last_observed_ms,
                "sample_rate_hz": s.sample_rate_hz,
                "channel_count": s.channel_count,
                "source_category": s.source_category,
                "apw:proof_level": s.proof_level,
            }
            for s in self.stems
        ]

        if self.export is not None:
            manifest["export"] = {
                "file_path": self.export.file_path,
                "file_name": self.export.file_name,
                "sha256": self.export.sha256,
                "format": self.export.format,
                "file_size_bytes": self.export.file_size_bytes,
                "duration_seconds": self.export.duration_seconds,
                "exported_at": self.export.exported_at,
                "apw:proof_level": "directly_observed",
            }

        if self.ingredients:
            manifest["ingredients"] = [
                {
                    "file_name": i.file_name,
                    "sha256": i.sha256,
                    "apw:proof_level": i.proof_level,
                    "correlation_confidence": i.correlation_confidence,
                    "audio_fingerprint": i.audio_fingerprint,
                }
                for i in self.ingredients
            ]

        if self.composite_edits:
            manifest["edit_history"] = self.composite_edits

        if self.hardware_binding is not None:
            manifest["hardware_binding"] = self.hardware_binding

        if self.time_anchors:
            manifest["time_anchors"] = self.time_anchors

        if self.forgery_report is not None:
            manifest["forgery_analysis"] = self.forgery_report

        manifest["apw:unobserved"] = self.unobserved

        manifest["c2pa_mapping"] = {
            "claim_generator": "AudioProvenanceCapture/0.2.0",
            "assertions": self._build_c2pa_assertions(),
        }

        return manifest

    def _build_c2pa_assertions(self) -> list[dict[str, object]]:
        """Map internal evidence to C2PA assertion structures.

        C2PA assertion types used:
            c2pa.hash.data     - content hash binding
            c2pa.ingredient    - sample/stem references
            c2pa.actions       - edit actions performed
            c2pa.asset         - the final output file

        Custom assertions (apw: namespace):
            apw.proof_level    - evidence confidence classification
            apw.hash_chain     - rolling hash chain summary
            apw.unobserved     - explicitly unknown/unobservable data
        """
        assertions: list[dict[str, object]] = []

        if self.export is not None:
            assertions.append({
                "label": "c2pa.hash.data",
                "data": {
                    "name": self.export.file_name,
                    "hash": self.export.sha256,
                    "algorithm": "sha256",
                },
            })

        for stem in self.stems:
            assertions.append({
                "label": "c2pa.ingredient",
                "data": {
                    "title": stem.stem_id,
                    "relationship": "componentOf",
                    "apw:hash_chain_root": stem.hash_chain_root,
                    "apw:proof_level": stem.proof_level,
                },
            })

        for ingredient in self.ingredients:
            assertions.append({
                "label": "c2pa.ingredient",
                "data": {
                    "title": ingredient.file_name,
                    "relationship": "inputTo",
                    "hash": ingredient.sha256,
                    "apw:proof_level": ingredient.proof_level,
                },
            })

        if self.composite_edits:
            actions = []
            for edit in self.composite_edits:
                actions.append({
                    "action": _c2pa_action_type(str(edit.get("edit_type", "unknown"))),
                    "when": edit.get("timestamp_ms"),
                    "apw:edit_type": edit.get("edit_type"),
                    "apw:confidence": edit.get("confidence"),
                    "apw:proof_level": "inferred",
                })
            assertions.append({
                "label": "c2pa.actions",
                "data": {"actions": actions},
            })

        assertions.append({
            "label": "apw.unobserved",
            "data": {"items": self.unobserved},
        })

        return assertions

    def write_json(self, path: Path) -> None:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = self.build()
        with path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        log.info("Manifest written to %s", path)


def _c2pa_action_type(edit_type: str) -> str:
    """Map internal edit types to C2PA action vocabulary.

    C2PA action types from the specification:
        c2pa.created, c2pa.edited, c2pa.published, c2pa.opened,
        c2pa.placed, c2pa.removed, c2pa.unknown
    """
    mapping = {
        "clip_paste": "c2pa.placed",
        "clip_delete": "c2pa.removed",
        "effect_change": "c2pa.edited",
        "sample_import_confirmed": "c2pa.placed",
        "arrangement_edit": "c2pa.edited",
        "undo": "c2pa.edited",
    }
    return mapping.get(edit_type, "c2pa.unknown")
