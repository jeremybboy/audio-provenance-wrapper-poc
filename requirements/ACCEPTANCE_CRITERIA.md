# Acceptance Criteria

## v0.1 - Pass-Through Plugin
- Plugin loads in Ableton Live.
- Audio passes through unchanged.
- Playback is stable.
- No crashes during playback.

## v0.2 - Event Logging
- Plugin timestamps observable events.
- Audio hashes are generated.
- Session identifiers are created.

## v0.3 - UDP Streaming
- Plugin sends UDP events.
- Local daemon receives events.
- Event logs persist locally.

## v0.4 - Export Detection
- Daemon detects exported WAV or AIFF files.
- Final exported file is hashed.

## v1.0 - Manifest Generation
- JSON manifest is automatically generated.
- Manifest contains:
  - observed stem hash
  - final export hash
  - timestamps
  - source category
  - proof levels
  - unknown or unobserved fields where appropriate

## Validation Principles
- Never overclaim provenance.
- Unknown data must remain unknown.
- Observed data must be explicitly identified.
