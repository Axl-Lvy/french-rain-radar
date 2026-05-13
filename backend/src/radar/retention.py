"""Delete frames older than the retention window and prune the manifest accordingly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def cleanup_layer(tile_dir: Path, layer: str, max_age: timedelta, manifest: dict) -> int:
    """Remove frames from ``manifest[layer]`` and the filesystem if older than ``max_age``.

    Returns the number of frames removed.
    """
    cutoff = datetime.now(UTC) - max_age
    kept: list[dict] = []
    removed = 0
    for frame in manifest["layers"].get(layer, {}).get("frames", []):
        ts = _parse_ts(frame["timestamp"])
        if ts >= cutoff:
            kept.append(frame)
            continue
        png = tile_dir / frame["url"]
        png.unlink(missing_ok=True)
        removed += 1
    manifest["layers"].setdefault(layer, {"frames": []})["frames"] = kept
    if removed:
        log.info("cleanup", layer=layer, removed=removed, remaining=len(kept))
    return removed
