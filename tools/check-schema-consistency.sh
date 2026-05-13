#!/usr/bin/env bash
# Validate the example manifest against the JSON schema.
# Used by CI; safe to run locally.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v check-jsonschema >/dev/null 2>&1; then
    echo "check-jsonschema not on PATH; falling back to uv run..."
    cd "$ROOT/backend" && uv run check-jsonschema \
        --schemafile "$ROOT/schema/manifest.schema.json" \
        "$ROOT/schema/examples/manifest.example.json"
else
    check-jsonschema \
        --schemafile "$ROOT/schema/manifest.schema.json" \
        "$ROOT/schema/examples/manifest.example.json"
fi
