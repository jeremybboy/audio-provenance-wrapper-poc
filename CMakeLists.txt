cmake_minimum_required(VERSION 3.22)

project(AudioProvenanceWrapperPoc
    VERSION 0.2.0
    LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(APPLE AND NOT DEFINED CMAKE_OSX_DEPLOYMENT_TARGET)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "12.0" CACHE STRING "Minimum macOS deployment target" FORCE)
endif()

set(APW_JUCE_DIR "" CACHE PATH "Path to a local JUCE checkout")

if(APW_JUCE_DIR)
    add_subdirectory("${APW_JUCE_DIR}" "${CMAKE_BINARY_DIR}/JUCE")
else()
    find_package(JUCE CONFIG QUIET)

    if(NOT JUCE_FOUND)
        message(FATAL_ERROR "JUCE not found. Re-run CMake with -DAPW_JUCE_DIR=/path/to/JUCE.")
    endif()
endif()

juce_add_plugin(AudioProvenanceCapture
    COMPANY_NAME "Audio Provenance POC"
    BUNDLE_ID "com.audioprovenance.capture"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE
    PLUGIN_MANUFACTURER_CODE ApPr
    PLUGIN_CODE ApCa
    FORMATS VST3
    PRODUCT_NAME "Audio Provenance Capture")

target_sources(AudioProvenanceCapture
    PRIVATE
        src/AudioObserver.cpp
        src/EventEmitter.cpp
        src/PluginEditor.cpp
        src/PluginProcessor.cpp)

target_include_directories(AudioProvenanceCapture
    PRIVATE
        src)

target_compile_definitions(AudioProvenanceCapture
    PUBLIC
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0
        JUCE_VST3_CAN_REPLACE_VST2=0)

target_link_libraries(AudioProvenanceCapture
    PRIVATE
        juce::juce_audio_processors
        juce::juce_cryptography
        juce::juce_dsp
        juce::juce_gui_basics
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)
