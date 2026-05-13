"""Delete sources older than the retention window plus their cached tile trees,
and prune the manifest accordingly.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _ts_url(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def cleanup_layer_v2(
    *,
    tile_dir: Path,
    layer: str,
    max_age_hours: int,
    manifest: dict,
) -> int:
    """Drop expired frames for one layer.

    For each frame older than ``max_age_hours``:

    - Remove its source file under ``tile_dir/sources/<layer>/<ts>.{h5,grib2}``
    - Remove its lazily-rendered tile cache under ``tile_dir/cache/<layer>/<ts>/``
    - Drop it from the manifest's frame list

    Returns the number of frames removed.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    frames_in = manifest.get("layers", {}).get(layer, {}).get("frames", [])
    if not frames_in:
        return 0

    sources_dir = tile_dir / "sources" / layer
    cache_dir = tile_dir / "cache" / layer

    kept: list[dict] = []
    removed = 0
    for frame in frames_in:
        ts = _parse_ts(frame["timestamp"])
        if ts >= cutoff:
            kept.append(frame)
            continue
        ts_url = _ts_url(ts)
        for suffix in (".h5", ".grib2"):
            src = sources_dir / f"{ts_url}{suffix}"
            src.unlink(missing_ok=True)
        cache_subdir = cache_dir / ts_url
        if cache_subdir.exists():
            shutil.rmtree(cache_subdir, ignore_errors=True)
        removed += 1

    manifest["layers"].setdefault(layer, {"frames": []})["frames"] = kept
    if removed:
        log.info("cleanup", layer=layer, removed=removed, remaining=len(kept))
    return removed
