"""Manifest reader/writer + schema validation.

The manifest is the contract between backend and clients. Every write is
atomic, and every write is validated against ``schema/manifest.schema.json``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "schema" / "manifest.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError on schema violations."""
    Draft202012Validator(load_schema()).validate(manifest)


def empty_manifest(*, bbox: dict[str, float], tile_size: dict[str, int], color_scale: str) -> dict[str, Any]:
    """Return a fresh, valid manifest with no frames."""
    return {
        "manifestVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "bbox": bbox,
        "tileSize": tile_size,
        "colorScale": color_scale,
        "layers": {
            "radar":    {"frames": []},
            "nowcast":  {"frames": []},
            "forecast": {"frames": []},
        },
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Validate and write ``manifest`` to ``path`` atomically."""
    validate_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix="manifest.json.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, indent=2)
        os.replace(tmp_str, path)
    except Exception:
        Path(tmp_str).unlink(missing_ok=True)
        raise


def read_manifest(path: Path) -> dict[str, Any]:
    """Read and validate a manifest from disk."""
    manifest = json.loads(path.read_text())
    validate_manifest(manifest)
    return manifest


def most_recent_timestamp(manifest: dict[str, Any], layer: str) -> datetime | None:
    """Return the timestamp of the newest frame in ``manifest['layers'][layer]``.

    Used by ingest commands to dedup against the publisher: if Météo-France's
    latest available frame timestamp equals this, there is no new data to
    download and the call can exit early.

    Returns ``None`` when the layer is missing or empty.
    """
    frames = manifest.get("layers", {}).get(layer, {}).get("frames", [])
    if not frames:
        return None
    latest = max(f["timestamp"] for f in frames)
    return datetime.fromisoformat(latest.replace("Z", "+00:00"))
