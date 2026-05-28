# audio-provenance-wrapper-poc

Proof of concept for audio provenance capture in Ableton Live using a wrapper/capture plugin, local daemon, audio hashing, and JSON manifests for stem-to-export traceability.

## Current State (v0.2)

### VST3 Capture Plugin (C++ / JUCE)

- Mono/stereo audio pass-through
- Rolling SHA-256 hash chain (4096-sample windows)
- Audio feature extraction: RMS, zero-crossing rate, spectral centroid, 3-band spectral profile
- Silence/audio transition detection
- Spectral profile change detection (EQ/filter/effect changes)
- Transport state tracking (play, stop, record, loop, BPM)
- MIDI event capture with CC knob-turn aggregation
- UDP event streaming to daemon (silence-throttled)

### Local Daemon (Python)

- **Evidence receiver**: UDP listener, event taxonomy validation, JSONL persistence
- **Sample watcher**: Filesystem monitoring, SHA-256 hashing, audio fingerprinting
- **Project differ**: Ableton .als gzip-XML parser, structural snapshot/diff
- **Correlation engine**: 6 rule-based edit detectors with confidence scoring
- **Forgery analysis**: Audio stream, input behavior, and hash chain integrity checks
- **Manifest builder**: C2PA-compatible crJSON with proof levels
- **Hardware attestation**: Software signing provider (Secure Enclave and TPM stubs ready)
- **Unified daemon process**: `python3 -m daemon` starts all components

### Scaffolded (interfaces defined, implementation pending)

- OS-level input capture (CGEventTap)
- Screen observer (screenshot-to-feature-vector)
- Secure Enclave / TPM hardware binding
- RFC 3161 + Roughtime time anchoring
- ARA 2 integration for cooperative DAWs

## macOS Build (Plugin)

Prerequisites: macOS with Xcode CLI tools, CMake 3.22+, local JUCE checkout.

```sh
cmake -S . -B build -DAPW_JUCE_DIR=/path/to/JUCE -DCMAKE_BUILD_TYPE=Debug
cmake --build build --target AudioProvenanceCapture_VST3 --config Debug
```

Install for Ableton:

```sh
mkdir -p "$HOME/Library/Audio/Plug-Ins/VST3"
cp -R "build/AudioProvenanceCapture_artefacts/Debug/VST3/Audio Provenance Capture.vst3" \
      "$HOME/Library/Audio/Plug-Ins/VST3/"
```

## Running the Daemon

```sh
python3 -m daemon \
  --port 9876 \
  --sample-dir ~/Music/ProvenanceSamples \
  --export-dir ~/Music/Exports \
  --project ~/Music/MyProject/MyProject.als \
  --manifest-dir manifests
```

The daemon listens for plugin UDP events, watches for sample imports and exports, monitors the .als project file for structural changes, and generates a C2PA-compatible manifest when an export is detected.

## Running Tests

```sh
python3 -m unittest discover -s tests
```

## Documentation

- `docs/ARCHITECTURE.md` - System architecture and trust boundary
- `docs/MULTI_LAYER_OBSERVATION.md` - Multi-layer edit observation design
- `docs/ROADMAP.md` - Sprint plan and version milestones
- `docs/MANIFEST_SCHEMA.md` - Manifest trust model
- `requirements/` - Product, technical, and acceptance requirements
