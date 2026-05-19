# Technical Requirements

## Plugin Framework
- JUCE
- VST3 support first
- AU support later

## Plugin Requirements
The plugin must:
- load in Ableton Live
- process audio in real time
- support pass-through audio
- optionally observe MIDI input
- timestamp observable events
- compute rolling audio hashes or fingerprints
- stream structured events externally

## Communication Layer
- local UDP messaging
- plugin sends events to a local daemon process
- low latency
- non-blocking

## Local Daemon
The daemon must:
- receive UDP events
- persist session state
- monitor export directories
- detect WAV or AIFF exports
- hash exported files
- generate JSON manifests

## Manifest Requirements
The manifest must:
- be JSON
- include proof levels
- include timestamps
- include export hashes
- include observed stem hashes
- support unknown or unobserved fields

## Hashing
Initial implementation:
- SHA-256

## Platform
Initial implementation target:
- macOS
- Ableton Live

## Initial Constraints
- one observed stem only
- no full DAW introspection
- no hidden plugin state assumptions
