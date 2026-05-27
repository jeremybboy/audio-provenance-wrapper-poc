from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """Every observation event produced by the plugin or daemon."""

    BUFFER_HASH = "buffer_hash"
    AUDIO_TRANSITION = "audio_transition"
    SPECTRAL_SHIFT = "spectral_shift"
    TRANSPORT_CHANGE = "transport_change"
    MIDI_EVENT = "midi_event"
    SESSION_CONFIG = "session_config_change"
    SAMPLE_FILE_OBSERVED = "sample_file_observed"
    INGREDIENT_CORRELATION = "ingredient_correlation"


class ProofLevel(str, Enum):
    """How confident the system is in a given claim."""

    DIRECTLY_OBSERVED = "directly_observed"
    INFERRED = "inferred"
    USER_DECLARED = "user_declared"
    EXTERNALLY_VERIFIED = "externally_verified"
    UNKNOWN_UNOBSERVED = "unknown_unobserved"


REQUIRED_FIELDS: dict[str, list[str]] = {
    EventType.BUFFER_HASH: [
        "window_hash",
        "prev_hash",
        "rms_level",
        "zero_crossing_rate",
    ],
    EventType.AUDIO_TRANSITION: ["direction", "boundary_hash"],
    EventType.SPECTRAL_SHIFT: [
        "prev_spectral_centroid_hz",
        "new_spectral_centroid_hz",
    ],
    EventType.TRANSPORT_CHANGE: ["transport_state"],
    EventType.MIDI_EVENT: ["midi_event_type", "midi_channel"],
    EventType.SESSION_CONFIG: ["sample_rate_hz", "channel_count"],
    EventType.SAMPLE_FILE_OBSERVED: ["sha256", "file_name"],
    EventType.INGREDIENT_CORRELATION: ["sample_sha256", "confidence"],
}

_VALID_EVENT_TYPES = frozenset(e.value for e in EventType)
_VALID_PROOF_LEVELS = frozenset(p.value for p in ProofLevel)


def validate_event(event: dict[str, object]) -> tuple[bool, str]:
    """Return (True, '') if the event is well-formed, else (False, reason)."""
    event_type = event.get("event_type")
    if event_type not in _VALID_EVENT_TYPES:
        return False, f"Unknown event type: {event_type}"

    proof_level = event.get("proof_level")
    if proof_level not in _VALID_PROOF_LEVELS:
        return False, f"Unknown proof level: {proof_level}"

    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        if field not in event:
            return False, f"Missing required field '{field}' for {event_type}"

    return True, ""
