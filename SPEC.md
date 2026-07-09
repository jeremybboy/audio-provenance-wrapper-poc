# Audio Provenance Wrapper POC - Build Spec

## Overview

Build out the audio-provenance-wrapper-poc from its current scaffolded state to a robust, testable system. The project captures provenance evidence from audio editing sessions in DAWs (primarily Ableton Live) using a multi-layer observation architecture.

## Current State

### Functional (working code with tests)
- **C++ VST3 plugin**: Pass-through audio, rolling SHA-256 hash chain, spectral features (RMS, ZCR, centroid, 3-band profile), silence/audio transitions, transport state, MIDI capture, CC knob-turn aggregation, spectral profile change detection, UDP event streaming, silence throttling
- **Evidence receiver**: UDP listener, event taxonomy validation, JSONL persistence
- **Sample watcher**: Filesystem monitoring, audio fingerprinting (RMS + ZCR), SHA-256 hashing
- **Sample correlator**: RMS/ZCR-based stream-to-sample matching
- **Correlation engine**: 6 rule-based detectors (clip paste/delete, effect change, sample import, undo, arrangement edit), temporal alignment, confidence scoring, composite edit evidence
- **Project differ**: Ableton .als gzip-XML parser, structural snapshot extraction, diff computation (tracks, clips, devices, samples, automation, MIDI, BPM, locators)
- **Forgery analysis**: Audio stream regularity, input behavior analysis (IKI, pauses, fatigue, skewness), hash chain integrity verification
- **Manifest builder**: C2PA-compatible crJSON with proof levels and unobserved fields
- **68 Python tests passing**

### Scaffolded (interfaces defined, stubs raise NotImplementedError)
- **Input capture**: CGEventTap observer (macOS), shortcut classifier, behavioral fingerprint
- **Screen observer**: Screenshot-to-feature-vector pipeline, perceptual hashing, adaptive capture rate
- **Hardware attestation**: Secure Enclave (macOS), TPM 2.0 (Linux), software fallback
- **Time anchoring**: RFC 3161 TSA client, Roughtime client, dual-anchor verification
- **ARA observer**: C++ header scaffold for ARA 2 integration

## What Needs to Be Built

### Priority 1: End-to-End Pipeline (make the demo work)

1. **Daemon orchestrator** - A single entry point (`daemon/main.py` or `daemon/__main__.py`) that starts all daemon components together: evidence receiver, sample watcher, project watcher, and correlation engine. Currently each module has its own `__main__.py` but there's no unified daemon process.

2. **Export watcher** - Extend the sample watcher or create a new module to watch the Ableton export directory for new WAV/AIFF files, hash them, and link them to the active session. This is Sprint 4 in the roadmap and is required for manifest generation.

3. **Session management** - Generate and track session IDs. The plugin should generate a session ID on instantiation and include it in every UDP event. The daemon should group events by session. Currently there is no session concept in the evidence stream.

4. **Manifest generation trigger** - When an export is detected, the daemon should automatically build a manifest from the session's evidence. Currently the ManifestBuilder exists but nothing calls it.

5. **Wire the project differ to the daemon** - The ProjectWatcher has a `run_forever()` loop but it only logs. It needs to emit events into the evidence JSONL and feed the correlation engine.

6. **Wire the correlation engine to the evidence stream** - The correlation engine exists but nothing feeds it. The evidence receiver should pass each validated event to the correlation engine.

### Priority 2: Implement the Software Key Provider

The `SoftwareProvider` in hardware_attestation is the development fallback. It should work without Secure Enclave or TPM so the hash chain signing flow can be tested end-to-end. Implement using Ed25519 (via `cryptography` package or pure Python `ed25519`). This is the minimum viable hardware abstraction.

### Priority 3: Robustness and Testing

1. **Integration test**: A test that simulates the full pipeline: send UDP events mimicking a plugin session, detect an export, generate a manifest, verify the manifest contains expected evidence.

2. **Project differ tests with real .als structure**: The current tests use synthetic ProjectSnapshot objects. Add tests that parse actual gzip-compressed XML matching the Ableton .als structure.

3. **Taxonomy completeness**: Ensure all event types produced by the C++ plugin (including `spectral_profile_change`, `parameter_change`) are validated by the daemon taxonomy and handled by the correlation engine.

4. **Error handling at boundaries**: The evidence receiver silently drops malformed packets. It should count and log error rates. The project watcher should handle corrupt .als files gracefully.

5. **README update**: The README still says "Not implemented yet: provenance capture, hashing, UDP, C2PA, local daemon". All of these are now at least partially implemented.

## Constraints

- **Python 3.10+** for daemon code (stdlib only for core; `cryptography` package acceptable for Ed25519)
- **C++17 with JUCE** for plugin code (do not modify C++ files in this build)
- **No external Python dependencies** for core observation modules (stdlib only)
- **macOS primary target** (Linux compatibility is nice-to-have)
- **Never claim what was not observed** - every event must carry a proof_level
- **Match existing code style**: logging via `logging` module, type hints, dataclasses, JSONL evidence format

## Success Criteria

1. `python3 -m daemon` starts a unified daemon that listens for UDP events, watches sample folders, watches a configured .als file, runs the correlation engine, and generates manifests on export detection.
2. All existing tests continue to pass.
3. New integration test demonstrates the end-to-end flow.
4. A manifest JSON file is produced when an export is simulated.
5. The README accurately describes the current state.
