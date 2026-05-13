# schema/

The single source of truth for the contract between backend and clients.

## Files

- `manifest.schema.json` — JSON Schema 2020-12 describing the manifest the backend writes and the clients read.
- `examples/manifest.example.json` — A valid example used by CI to verify both sides remain in sync.

## Versioning

The schema carries a `manifestVersion` integer.

- **Compatible additions** (new optional fields, new layer kinds): keep `manifestVersion` unchanged.
- **Breaking changes** (rename / remove / type change): bump `manifestVersion` and accept the previous one for one release while clients update.

## Validation

Backend validates every manifest it writes against the schema (see `radar.manifest.validate_manifest`).
Clients deserialize with `kotlinx-serialization`; a `ManifestSchemaConsistencyTest` in `:shared` decodes the example and fails CI if the Kotlin model drifts.
