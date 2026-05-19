# Sample Import Provenance Spike Validation

This spike adds a local sample-folder watcher only. It does not modify the VST plugin, add C2PA signing, add wrapper or mini-host behavior, or claim exact Ableton track attribution.

## Watcher Command

From the repository root:

```sh
python3 -m daemon.sample_watcher \
  --watch-dir "$HOME/Music/ProvenanceSamples" \
  --evidence-file evidence/sample_import_events.jsonl
```

The watcher records `.wav`, `.aiff`, `.aif`, `.mp3`, and `.m4a` files. WAV and AIFF metadata is extracted with Python standard-library readers; other formats use macOS `afinfo` when available and otherwise leave unavailable metadata as `null`.

## Manual Test

1. Create a test folder, for example `~/Music/ProvenanceSamples`.
2. Start the daemon watcher with the command above.
3. Drag or copy an audio file into that folder.
4. Drag that same file into Ableton.
5. Confirm `evidence/sample_import_events.jsonl` contains file metadata and a SHA-256 hash.
6. Confirm the record does not claim that the sample was placed on a specific Ableton track.

## Expected Evidence Record

Each JSONL row is an internal evidence record with `event_type` set to `sample_file_observed` and `proof_level` set to `directly_observed`.

Each row includes the observed file path, file name, `format`, `file_extension`, byte size, creation timestamp, modification timestamp, observation timestamp, and SHA-256 hash.

The record may include `duration_seconds`, `sample_rate`, and `channels` when the local machine can extract those values. Missing audio metadata must remain `null`.

The notes must preserve the limitation that filesystem observation does not prove exact Ableton track attribution. Any future association between sample import and plugin activity must be labeled `inferred`.

## Automated Smoke Test

From the repository root:

```sh
python3 -m unittest tests.test_sample_watcher
```
