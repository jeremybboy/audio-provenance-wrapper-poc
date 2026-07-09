#pragma once

/*  ARA (Audio Random Access) Observer Scaffold
 *
 *  ARA is a Celemony-developed plugin extension supported by Logic Pro,
 *  Studio One, Cubase, Reaper, and Cakewalk.  An ARA-enabled plugin
 *  receives direct access to the DAW's audio editing model:
 *
 *      - Audio region boundaries and positions on the timeline
 *      - Time-stretch and pitch-shift parameters per region
 *      - Edit operations (split, merge, move, resize)
 *      - The full arrangement structure
 *      - Offline access to source audio before and after edits
 *
 *  This gives proof_level "directly_observed" for edit operations --
 *  categorically stronger than the "inferred" level from input capture,
 *  screen observation, or project file diffing.
 *
 *  Ableton Live does NOT support ARA.  For Ableton, the other observation
 *  layers remain the primary evidence source.
 *
 *  ──────────────────────────────────────────────────────────────────
 *  ARA SDK integration requirements
 *  ──────────────────────────────────────────────────────────────────
 *
 *  1. Link against the ARA SDK (https://github.com/Celemony/ARA_SDK).
 *     The SDK provides C headers (ARAInterface.h) and C++ wrappers.
 *
 *  2. Implement ARADocumentControllerInterface callbacks:
 *
 *     - willAddMusicalContextToDocument / didAddMusicalContextToDocument
 *       → Emits session_config_change (tempo, time signature)
 *
 *     - willAddAudioSourceToDocument / didAddAudioSourceToDocument
 *       → Emits sample_file_observed with direct file reference
 *
 *     - willAddAudioModificationToAudioSource
 *       → Emits audio_modification_created (time-stretch, pitch-shift params)
 *
 *     - willAddPlaybackRegionToRegionSequence
 *       → Emits region_added (timeline position, duration, source ref)
 *
 *     - willRemovePlaybackRegionFromRegionSequence
 *       → Emits region_removed
 *
 *     - willUpdatePlaybackRegionProperties
 *       → Emits region_modified (position change, duration change, etc.)
 *
 *     - willUpdateAudioModificationProperties
 *       → Emits modification_changed (time-stretch or pitch-shift delta)
 *
 *     - willUpdateAudioSourceProperties
 *       → Emits source_changed (sample rate, channel count, name)
 *
 *  3. Serialize ARA events as JSON using the same ObservationEvent format
 *     and stream them to the daemon via the existing EventEmitter (UDP).
 *
 *  ──────────────────────────────────────────────────────────────────
 *  ARA event taxonomy (extends the base taxonomy)
 *  ──────────────────────────────────────────────────────────────────
 *
 *  All ARA events carry proof_level "directly_observed" because the DAW
 *  explicitly notifies the plugin of each operation.
 *
 *  | Event Type                    | ARA Callback Source                     |
 *  |-------------------------------|-----------------------------------------|
 *  | ara_region_added              | didAddPlaybackRegionToRegionSequence    |
 *  | ara_region_removed            | willRemovePlaybackRegion...             |
 *  | ara_region_modified           | willUpdatePlaybackRegionProperties      |
 *  | ara_modification_created      | willAddAudioModificationToAudioSource   |
 *  | ara_modification_changed      | willUpdateAudioModificationProperties   |
 *  | ara_source_added              | didAddAudioSourceToDocument             |
 *  | ara_source_changed            | willUpdateAudioSourceProperties         |
 *  | ara_context_changed           | willUpdateMusicalContextProperties      |
 *
 *  ──────────────────────────────────────────────────────────────────
 *  DAW compatibility
 *  ──────────────────────────────────────────────────────────────────
 *
 *  | DAW           | ARA Support | Notes                              |
 *  |---------------|:-----------:|------------------------------------|
 *  | Logic Pro     | Yes (ARA 2) | Since 10.5.1                       |
 *  | Studio One    | Yes (ARA 2) | Native, Celemony partnership       |
 *  | Cubase/Nuendo | Yes (ARA 2) | Since Cubase 13                    |
 *  | Reaper        | Yes (ARA 2) | Since 7.0                          |
 *  | Cakewalk      | Yes (ARA 2) | Since 2019.09                      |
 *  | Ableton Live  | No          | Use other observation layers        |
 *  | Bitwig        | No          | Use other observation layers        |
 *  | FL Studio     | No          | Use other observation layers        |
 *  | Pro Tools     | No          | AAX-only ecosystem                  |
 *
 *  ──────────────────────────────────────────────────────────────────
 *  Build integration
 *  ──────────────────────────────────────────────────────────────────
 *
 *  The ARA observer should be conditionally compiled behind a CMake option:
 *
 *      option(APW_ENABLE_ARA "Enable ARA 2 integration" OFF)
 *
 *  When enabled, add the ARA SDK include path and link the ARA library.
 *  When disabled, the plugin builds and operates exactly as it does now,
 *  using only the audio buffer observation pipeline.
 */

#if defined(APW_ENABLE_ARA) && APW_ENABLE_ARA

#include <juce_audio_processors/juce_audio_processors.h>

namespace apw
{

/*  Stub: ARAObserver class declaration.
 *
 *  When APW_ENABLE_ARA is set, this class implements the
 *  ARADocumentControllerInterface callbacks and translates them into
 *  JSON events for the EventEmitter.
 *
 *  Implementation requires:
 *      1. ARA SDK headers on the include path
 *      2. JUCE ARA support (juce_audio_processors has ARA wrappers)
 *      3. EventEmitter instance for UDP streaming
 *
 *  See JUCE's ARADocumentControllerSpecialisation for the base class.
 */

} // namespace apw

#endif // APW_ENABLE_ARA
