"""Lazy XYZ tile renderer.

Caddy reverse-proxies ``/{layer}/{timestamp}/{z}/{x}/{y}.png`` to this service
only on cache-miss (Caddy's ``file`` matcher handles the cache-hit path). The
service:

1. Loads the cached source file for ``(layer, timestamp)`` from
   ``$RADAR_TILE_DIR/sources/<layer>/<ts>.{h5,grib2}``.
2. Reprojects + colourises the requested tile.
3. Saves the PNG to ``$RADAR_TILE_DIR/cache/<layer>/<ts>/<z>/<x>/<y>.png``
   so future requests bypass us via Caddy's static-file path.
4. Returns the PNG bytes to Caddy.

The service is single-process by default (uvicorn) and stateless; restarting
it loses no work.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import Response

from .config import Settings, get_settings
from .grib import read_arome_pi_precip
from .radar_hdf5 import mm_per_window_to_mm_per_hour, read_mosaic
from .tiles import render_tile_lonlat, render_tile_projected

log = structlog.get_logger(__name__)
app = FastAPI(title="French rain radar tile server", docs_url=None, redoc_url=None)

# Lazy memoised loaders: ``(layer, timestamp) -> field``. Keep only the most
# recently used few since the source files are small (2 MB radar, sub-MB GRIB).
_RECENT_SOURCES_CAP = 8
_recent_sources: dict[tuple[str, str], object] = {}


_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
_LAYERS = {"radar", "nowcast", "forecast"}


def _ts_url_to_datetime(ts_url: str) -> datetime:
    """Parse the URL-safe ``YYYY-MM-DDTHH-MM-SSZ`` form."""
    if not _TS_RE.match(ts_url):
        raise HTTPException(400, f"bad timestamp format: {ts_url!r}")
    date_part, time_part = ts_url.split("T")
    h, m, s = time_part.rstrip("Z").split("-")
    return datetime.fromisoformat(f"{date_part}T{h}:{m}:{s}+00:00")


def _source_path(settings: Settings, layer: str, ts_url: str) -> Path | None:
    base = settings.tile_dir / "sources" / layer
    for suffix in (".h5", ".grib2"):
        p = base / f"{ts_url}{suffix}"
        if p.exists():
            return p
    return None


def _load_source(layer: str, source_path: Path) -> object:
    """Read a cached source file. Returns either ``RadarMosaic`` or ``PrecipField``."""
    if source_path.suffix == ".h5":
        return read_mosaic(source_path)
    if source_path.suffix == ".grib2":
        return read_arome_pi_precip(source_path)
    raise HTTPException(500, f"unrecognised source suffix: {source_path}")


def _get_source(layer: str, ts_url: str, source_path: Path) -> object:
    key = (layer, ts_url)
    if key in _recent_sources:
        return _recent_sources[key]
    src = _load_source(layer, source_path)
    if len(_recent_sources) >= _RECENT_SOURCES_CAP:
        _recent_sources.pop(next(iter(_recent_sources)))
    _recent_sources[key] = src
    return src


def _cache_path(settings: Settings, layer: str, ts_url: str, z: int, x: int, y: int) -> Path:
    return settings.tile_dir / "cache" / layer / ts_url / f"{z}/{x}/{y}.png"


def _write_atomic(dest: Path, payload: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=dest.name + ".", suffix=".tmp", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(payload)
        os.chmod(tmp_str, 0o644)
        os.replace(tmp_str, dest)
    except Exception:
        Path(tmp_str).unlink(missing_ok=True)
        raise


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "now": datetime.now(UTC).isoformat()}


@app.get("/{layer}/{timestamp}/{z}/{x}/{y}.png")
def get_tile(
    layer: str = PathParam(..., pattern=r"^(radar|nowcast|forecast)$"),
    timestamp: str = PathParam(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$"),
    z: int = PathParam(..., ge=0, le=14),
    x: int = PathParam(..., ge=0),
    y: int = PathParam(..., ge=0),
) -> Response:
    """Render one tile (cached on disk for subsequent identical requests)."""
    if layer not in _LAYERS:
        raise HTTPException(404, "unknown layer")
    # XYZ tile grid at zoom z has 2**z tiles along each axis; reject anything
    # outside that range up-front so we don't waste a render + disk write on a
    # request that can only produce a blank tile, and so attackers can't pollute
    # the on-disk cache with arbitrary (x, y) combinations.
    if x >= (1 << z) or y >= (1 << z):
        raise HTTPException(404, "tile out of range")
    settings = get_settings()
    cache = _cache_path(settings, layer, timestamp, z, x, y)
    if cache.exists():
        # We could let Caddy intercept first, but if this code is hit anyway
        # (warm path through proxy), short-circuit with the file's bytes.
        return Response(content=cache.read_bytes(), media_type="image/png")

    source_path = _source_path(settings, layer, timestamp)
    if source_path is None:
        raise HTTPException(404, f"no source for {layer}/{timestamp}")

    src = _get_source(layer, timestamp, source_path)

    if source_path.suffix == ".h5":
        from pyproj import Transformer
        to_src = Transformer.from_crs("EPSG:4326", src.proj_def, always_xy=True)  # type: ignore[attr-defined]
        ul_x, ul_y = to_src.transform(src.ul_lon, src.ul_lat)  # type: ignore[attr-defined]
        png = render_tile_projected(
            values=src.values * mm_per_window_to_mm_per_hour(5),  # type: ignore[attr-defined]
            src_crs=src.proj_def,  # type: ignore[attr-defined]
            src_origin_x=ul_x,
            src_origin_y=ul_y,
            src_xscale=src.x_scale,  # type: ignore[attr-defined]
            src_yscale=src.y_scale,  # type: ignore[attr-defined]
            z=z, x=x, y=y,
            color_scale=settings.color_scale,
        )
    else:
        png = render_tile_lonlat(
            values=src.values,        # type: ignore[attr-defined]
            src_lats=src.lats,        # type: ignore[attr-defined]
            src_lons=src.lons,        # type: ignore[attr-defined]
            z=z, x=x, y=y,
            color_scale=settings.color_scale,
        )

    _write_atomic(cache, png)
    log.debug("tile.rendered", layer=layer, ts=timestamp, z=z, x=x, y=y, bytes=len(png))
    return Response(content=png, media_type="image/png")
