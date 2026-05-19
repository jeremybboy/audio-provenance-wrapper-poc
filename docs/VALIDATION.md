# Validation

This page documents manual validation for Issue #4, Epic 1 - JUCE Plugin Scaffold.

Scope is intentionally limited to a stable VST3 pass-through plugin. This milestone does not implement provenance capture, hashing, UDP, C2PA, daemon behavior, or wrapper-host plugin loading.

## Epic 2 - Audio Pass-Through Validation

This section records manual Ableton Live validation for GitHub issue `#5`, Epic 2 - Audio Pass-Through.

The current plugin is only a transparent pass-through interception point. It does not capture provenance, hash audio, send UDP events, host wrapped plugins, inspect downstream devices, or generate manifests.

### Manual Ableton Validation Reference

Manual validation was reported on 2026-05-19 using an Ableton Live device chain:

```text
Audio Provenance Capture -> Channel EQ -> Limiter
```

The validation screenshot shows the `Audio Provenance Capture` VST3 inserted before Ableton `Channel EQ` and `Limiter`, the plugin editor open, stereo audio clips playing, and active level meters after the plugin chain.

### Validation Workflow

1. Build the VST3 plugin using the Milestone A build steps below.
2. Copy `Audio Provenance Capture.vst3` into `~/Library/Audio/Plug-Ins/VST3/`.
3. Open Ableton Live and rescan VST3 plugins.
4. Add an audio clip to an audio track.
5. Insert `Audio Provenance Capture` as the first device on the track.
6. Insert `Channel EQ` after the plugin.
7. Insert `Limiter` after `Channel EQ`.
8. Start playback.
9. Open the plugin UI.
10. Confirm audio meters remain active through the downstream Ableton devices.
11. Confirm stereo playback remains audible and stable.
12. Stop and restart playback to check basic transport stability.

### Validation Checklist

- [x] Plugin loads successfully in Ableton Live.
- [x] Plugin UI opens correctly.
- [x] Audio passes through the plugin.
- [x] Downstream `Channel EQ` receives signal after the plugin.
- [x] Downstream `Limiter` receives signal after `Channel EQ`.
- [x] Stereo playback works.
- [x] Audio meters show active signal flow.
- [x] No crash was observed during playback.
- [x] No provenance, hashing, UDP, C2PA, or wrapper-host behavior is claimed by this validation.

### Expected Results

- Ableton lists and loads `Audio Provenance Capture` as a VST3 plugin.
- The plugin editor opens and displays the v0.1 pass-through status.
- Audio remains audible when the plugin is active.
- Downstream Ableton devices continue receiving signal.
- Playback does not crash during the tested session.

### Known Limitations

- This validation is manual Ableton validation, not automated audio null testing.
- The screenshot supports the observed device-chain setup and active signal flow, but it does not prove bit-perfect sample identity by itself.
- No provenance events are produced yet.
- No audio hashes or fingerprints are produced yet.
- No UDP communication or daemon integration exists yet.
- No C2PA manifest or JSON provenance output exists yet.
- No wrapper-host plugin loading exists yet.
- Hidden Ableton state, hidden plugin state, preset identity, sample license, and upstream source provenance remain unknown and unobserved.

## Milestone A - JUCE Project Builds Successfully

### Manual Test

From the repository root on macOS:

```sh
cmake -S . -B build -DAPW_JUCE_DIR=/Users/uzanj/Downloads/JUCE -DCMAKE_BUILD_TYPE=Debug
cmake --build build --target AudioProvenanceCapture_VST3 --config Debug
```

If JUCE is somewhere else, replace `/Users/uzanj/Downloads/JUCE` with that local checkout path.

### Expected Result

CMake configures cleanly and produces `Audio Provenance Capture.vst3` under the build artefacts directory.

### Local Result

Validated on 2026-05-19 with JUCE at `/Users/uzanj/Downloads/JUCE`. Configure and VST3 build completed successfully, and `codesign --verify --deep --strict` passed for the generated bundle.

### Likely Failure Modes

- JUCE is missing or `APW_JUCE_DIR` points at the wrong directory.
- Xcode Command Line Tools are missing or not selected.
- CMake is too old to support the project.
- macOS blocks writes to the selected build directory.

## Milestone B - Plugin Loads in Ableton Live

Codex cannot complete this milestone from the shell. It requires manual validation in Ableton Live.

### Manual Test

1. Build Milestone A.
2. Copy the built VST3 bundle into `~/Library/Audio/Plug-Ins/VST3/`.
3. Open Ableton Live.
4. Open `Live > Settings > Plug-Ins` or `Live > Preferences > Plug-Ins`, depending on Ableton version.
5. Enable VST3 system folders and rescan plug-ins.
6. Search for `Audio Provenance Capture`.
7. Insert it on an audio track.

### Expected Result

Ableton lists the plugin and opens a small editor showing the v0.1 pass-through status.

### Likely Failure Modes

- The VST3 bundle was copied to the wrong folder.
- Ableton has VST3 system folders disabled.
- Ableton needs a full rescan or restart.
- The plugin failed validation because the local build is stale or incomplete.

## Milestone C - Audio Passes Through Unchanged

Codex cannot complete this milestone from the shell. It requires manual validation in Ableton Live.

### Manual Test

1. Add a known audio clip to an Ableton audio track.
2. Play the clip without the plugin and note the audible level and meter behavior.
3. Insert `Audio Provenance Capture` on the same track.
4. Toggle the plugin on and off during playback.
5. For a stricter check, duplicate the track, put the plugin on only one copy, invert polarity on one track with Ableton Utility, and play both together.

### Expected Result

The normal listening test should sound unchanged. In the polarity-cancel test, matching audio should cancel to silence or near-silence.

### Likely Failure Modes

- Host routing differs between the two tracks.
- A gain, pan, warp, or Utility setting differs between the reference and plugin paths.
- The plugin is inserted on the wrong track.
- Mono/stereo routing does not match.

## Milestone D - Plugin Survives Playback Start/Stop and Project Reload

Codex cannot complete this milestone from the shell. It requires manual validation in Ableton Live.

### Manual Test

1. Insert the plugin on an audio track.
2. Start and stop playback repeatedly.
3. Loop a section for several minutes.
4. Save the Ableton set.
5. Close and reopen Ableton.
6. Reload the set and start playback again.

### Expected Result

Ableton reloads the set, the plugin remains inserted, the editor opens, and playback continues without crashes or audio interruption.

### Likely Failure Modes

- Ableton rescans and rejects an older copied bundle.
- The plugin bundle was moved or deleted after saving the set.
- A local debug build was replaced while Ableton was still open.
- The test set uses unsupported routing outside mono or stereo audio tracks.
