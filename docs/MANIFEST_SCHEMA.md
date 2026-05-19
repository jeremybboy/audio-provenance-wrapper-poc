# Manifest Schema

## Purpose

Define the v0 manifest strategy for the Ableton audio provenance proof of concept.

The system maintains:
1. an internal provenance record
2. a minimal C2PA-compatible crJSON export

## Core Principle

Do not invent a separate manifest ecosystem.

The system captures provenance internally and serializes selected evidence into C2PA-compatible crJSON structures.

## Architecture

```text
Capture Plugin
→ Internal Provenance Record
→ C2PA/crJSON Export Layer
→ Final Manifest
```

## Internal Provenance Record

The internal provenance record is the primary truth model.

It stores:
- session identifiers
- stem identifiers
- timestamps
- observed hashes
- source categories
- proof levels
- export relationships
- unknown or bypassed states

This model is intentionally richer than the exported C2PA manifest.

## v0 C2PA/crJSON Export

The v0 implementation exports a simplified C2PA-compatible crJSON manifest.

## Required crJSON Structure

- `@context`
- `manifests[]`
- `label`
- `assertions`
- `claim.v2`
- `signature`
- `validationResults`

## Required Assertions

### `c2pa.hash.data`

Used for:
- final exported WAV or AIFF hash
- observed stem hash

### `c2pa.asset-ref`

Used for:
- exported asset reference

### `c2pa.asset-type.v2`

Used for:
- asset type classification

### `c2pa.actions.v2`

Used for:
- provenance actions
- creation events
- routing observations
- source classifications

## Optional Future Assertions

### `c2pa.ingredient.v3`

Potential future use:
- stems
- imported samples
- upstream assets
- generators

### `c2pa.hash.collection.data`

Potential future use:
- multi-stem workflows
- grouped exports

## Source Category Mapping

The system maps source categories to IPTC Digital Source Types where possible.

Examples:
- digitalCapture
- compositeSynthetic
- algorithmicMedia

## Proof Level Model

Proof levels are part of the internal provenance model.

They may later be exported through:
- custom assertion extensions
- action parameters
- extras blocks

Proof levels:
- directly_observed
- inferred
- user_declared
- externally_verified
- unknown_unobserved

## v0 Scope

v0 only requires:
- one observed stem
- one exported asset
- one minimal manifest
- one observed hash
- one action assertion

## v0 Example

The v0 manifest should demonstrate:
- exported asset hash
- observed stem hash
- timestamped action
- source category
- minimal claim metadata

## Future Expansion

Future versions may support:
- multiple ingredients
- multi-stem manifests
- richer action graphs
- embedded manifests
- signed manifests
- DAW operation history
- plugin-host provenance
