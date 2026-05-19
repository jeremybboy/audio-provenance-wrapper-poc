# audio-provenance-wrapper-poc

Proof of concept for audio provenance capture in Ableton Live using a wrapper/capture plugin, local daemon, audio hashing, and JSON manifests for stem-to-export traceability.

## Current Scope

The current implementation is Issue #4, Epic 1: a minimal JUCE VST3 pass-through plugin scaffold.

Implemented:
- JUCE CMake project scaffold
- VST3 plugin target
- `PluginProcessor` and `PluginEditor`
- Mono/stereo audio pass-through

Not implemented yet:
- provenance capture
- hashing
- UDP
- C2PA
- local daemon
- wrapper-host plugin loading

## macOS Build

Prerequisites:
- macOS with Xcode or Xcode Command Line Tools
- CMake 3.22 or newer
- a local JUCE checkout

Configure and build:

```sh
cmake -S . -B build -DAPW_JUCE_DIR=/Users/uzanj/Downloads/JUCE -DCMAKE_BUILD_TYPE=Debug
cmake --build build --target AudioProvenanceCapture_VST3 --config Debug
```

If JUCE is installed somewhere else, replace `/Users/uzanj/Downloads/JUCE` with that path.

## Ableton Local Testing

After building, copy the generated VST3 bundle into the user VST3 folder:

```sh
mkdir -p "$HOME/Library/Audio/Plug-Ins/VST3"
cp -R "build/AudioProvenanceCapture_artefacts/Debug/VST3/Audio Provenance Capture.vst3" "$HOME/Library/Audio/Plug-Ins/VST3/"
```

Then open Ableton Live, enable VST3 system folders in plug-in settings, rescan plug-ins, and insert `Audio Provenance Capture` on an audio track.

Expected v0.1 behavior: the plugin loads, displays a small pass-through editor, and leaves mono or stereo audio unchanged.

See `docs/VALIDATION.md` for milestone-by-milestone manual validation steps and failure modes.
