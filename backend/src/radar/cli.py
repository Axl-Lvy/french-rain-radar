"""Command-line entry point. Each subcommand is what its matching systemd timer calls.

Ingest commands only **download the source** (GRIB / HDF5) and update the
manifest with the available timestamps; tile rendering happens on demand via
``radar tile-server``.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog
import typer

from . import __version__
from .config import Bbox, Settings, get_settings
from .manifest import (
    MANIFEST_VERSION,
    empty_manifest,
    most_recent_timestamp,
    read_manifest,
    replace_layer_frames,
    touch_generated_at,
    upsert_layer_frame,
    write_manifest,
)

app = typer.Typer(help="French rain radar pipeline.", add_completion=False)
log = structlog.get_logger(__name__)

# Number of consecutive radar frames pysteps LK uses for motion estimation. 4
# covers ~15 min of history at the 5-min radar cadence — long enough to
# average out single-frame noise, short enough that the "steady motion"
# assumption still holds.
NOWCAST_HISTORY = 4

# Halve radar resolution (500 m -> 1 km) before pysteps LK. Full 3472x3472
# float32 stacks plus opencv pyramids OOM-kill the service on the cheap VPS.
# Nowcast skill at the 0-60 min horizon barely budges at 1 km vs 500 m.
NOWCAST_DOWNSAMPLE = 2


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), stream=sys.stderr, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    settings = get_settings()
    _configure_logging("DEBUG" if verbose else settings.log_level)


@app.command()
def version() -> None:
    """Print the package version and exit."""
    typer.echo(__version__)


# ----- shared helpers -----------------------------------------------------


def _bbox_tuple(b: Bbox) -> tuple[float, float, float, float]:
    return (b.lon_min, b.lat_min, b.lon_max, b.lat_max)


def _ts_url(ts: datetime) -> str:
    """URL-safe ISO timestamp: ``YYYY-MM-DDTHH-MM-SSZ`` (no colons)."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _source_path(settings: Settings, layer: str, ts: datetime, suffix: str) -> Path:
    return settings.tile_dir / "sources" / layer / f"{_ts_url(ts)}{suffix}"


def _load_or_init_manifest(settings: Settings) -> tuple[Path, dict]:
    manifest_path = settings.tile_dir / "manifest.json"
    if manifest_path.exists():
        try:
            m = read_manifest(manifest_path)
            if m.get("manifestVersion") == MANIFEST_VERSION:
                return manifest_path, m
            log.warning("manifest.version-mismatch.rebuilding", saw=m.get("manifestVersion"))
        except Exception as e:
            log.warning("manifest.invalid.rebuilding", error=str(e))
    bbox = {
        "latMin": settings.bbox.lat_min, "latMax": settings.bbox.lat_max,
        "lonMin": settings.bbox.lon_min, "lonMax": settings.bbox.lon_max,
    }
    return manifest_path, empty_manifest(bbox=bbox, color_scale=settings.color_scale)


# ----- ingest commands ---------------------------------------------------


@app.command("ingest-radar")
def ingest_radar() -> None:
    """Download the latest radar mosaic HDF5 to the source cache, update manifest.

    Idempotent: if Météo-France's latest frame is the one already in the
    manifest, this exits without downloading the payload.
    """
    from .meteofrance import MeteoFranceClient

    settings = get_settings()
    manifest_path, manifest = _load_or_init_manifest(settings)
    known_latest = most_recent_timestamp(manifest, "radar")

    with MeteoFranceClient(
        arome_token=settings.meteofrance_token_arome,
        radar_token=settings.meteofrance_token_radar,
    ) as mf:
        new_validity = mf.latest_radar_validity()
        if new_validity is None:
            log.warning("radar.descriptor.no-validity-time")
            return
        if known_latest and new_validity <= known_latest:
            log.info("radar.skip.same-validity", validity=new_validity.isoformat())
            return

        dest = _source_path(settings, "radar", new_validity, ".h5")
        mf.fetch_latest_radar(dest=dest)

    upsert_layer_frame(
        manifest, "radar",
        timestamp=new_validity,
        tile_url_template="radar/{timestamp}/{z}/{x}/{y}.png",
        min_zoom=settings.min_zoom,
        max_zoom=settings.max_zoom,
    )
    touch_generated_at(manifest)
    write_manifest(manifest_path, manifest)
    log.info("radar.frame.saved", validity=new_validity.isoformat(), path=str(dest))


@app.command("ingest-arome")
def ingest_arome() -> None:
    """Download the latest AROME-PI run and update manifest.

    Handles two cases:

    - **New run**: drop all previous forecast sources + cached tiles, then
      fetch every published leadtime (404s for unpublished leadtimes are
      silently skipped).
    - **Same run, partial**: top up — only fetch leadtimes whose source file
      isn't already on disk. Useful because AROME-PI publishes leadtimes
      incrementally over the hour after the run reference time.
    """
    import shutil
    from datetime import timedelta

    from .meteofrance import AROME_LEAD_TIMES_S, MeteoFranceClient

    settings = get_settings()
    manifest_path, manifest = _load_or_init_manifest(settings)

    with MeteoFranceClient(
        arome_token=settings.meteofrance_token_arome,
        radar_token=settings.meteofrance_token_radar,
    ) as mf:
        latest_run = mf.latest_arome_run()
        if latest_run is None:
            log.warning("no AROME-PI runs available")
            return

        run_iso = latest_run.isoformat().replace("+00:00", "Z")
        existing_run = manifest.get("layers", {}).get("forecast", {}).get("runTime")
        new_run = existing_run != run_iso

        if new_run:
            log.info("arome.new-run", run=run_iso, previous=existing_run)
            shutil.rmtree(settings.tile_dir / "sources" / "forecast", ignore_errors=True)
            shutil.rmtree(settings.tile_dir / "cache" / "forecast", ignore_errors=True)
        else:
            log.info("arome.top-up", run=run_iso)

        forecast_src_dir = settings.tile_dir / "sources" / "forecast"
        forecast_src_dir.mkdir(parents=True, exist_ok=True)
        valid_times: list[datetime] = []
        for lead in AROME_LEAD_TIMES_S:
            valid_time = latest_run + timedelta(seconds=lead)
            target = _source_path(settings, "forecast", valid_time, ".grib2")
            if target.exists():
                valid_times.append(valid_time)
                continue
            frame = mf.fetch_arome_leadtime(
                latest_run, lead,
                bbox=_bbox_tuple(settings.bbox),
                dest_dir=forecast_src_dir,
            )
            if frame is None:
                continue
            if frame.path != target:
                frame.path.rename(target)
            valid_times.append(valid_time)

    replace_layer_frames(
        manifest, "forecast",
        timestamps=valid_times,
        tile_url_template="forecast/{timestamp}/{z}/{x}/{y}.png",
        min_zoom=settings.min_zoom,
        max_zoom=settings.max_zoom,
        run_time=latest_run,
    )
    touch_generated_at(manifest)
    write_manifest(manifest_path, manifest)
    log.info("arome.run.saved", run=run_iso, frames=len(valid_times))


@app.command("nowcast")
def nowcast() -> None:
    """Run pysteps optical-flow extrapolation on the latest radar frames.

    Reads the last ``NOWCAST_HISTORY`` observed radar sources, extrapolates
    them 0-60 min ahead at 5-min steps, and writes 12 predicted ODIM_H5
    frames to ``sources/nowcast/`` for the tile server to render on demand.

    Each invocation **replaces** all previous nowcast frames and their cached
    tiles — old extrapolations are stale once a new radar frame arrives.

    Requires the optional ``nowcast`` extra (pysteps). Without it, logs a
    warning and exits 0 so the systemd timer stays green on installs that
    deliberately skip the extra.
    """
    import shutil

    from . import nowcast as nowcast_mod
    from .radar_hdf5 import downsample_mosaic, read_mosaic, write_mosaic

    settings = get_settings()
    manifest_path, manifest = _load_or_init_manifest(settings)

    radar_dir = settings.tile_dir / "sources" / "radar"
    if not radar_dir.exists():
        log.warning("nowcast.skip.no-radar-sources")
        return

    radar_files = sorted(radar_dir.glob("*.h5"))[-NOWCAST_HISTORY:]
    if len(radar_files) < 2:
        log.warning("nowcast.skip.insufficient-frames", have=len(radar_files), need=2)
        return

    mosaics = [read_mosaic(p) for p in radar_files]
    if NOWCAST_DOWNSAMPLE > 1:
        mosaics = [downsample_mosaic(m, NOWCAST_DOWNSAMPLE) for m in mosaics]
    seed = mosaics[-1]

    try:
        predicted = list(nowcast_mod.extrapolate(
            [m.values for m in mosaics],
            base_time=seed.timestamp,
            step_min=5,
            lead_time_min=60,
        ))
    except ModuleNotFoundError as e:
        log.warning("nowcast.skip.pysteps-missing", error=str(e))
        return

    nowcast_src_dir = settings.tile_dir / "sources" / "nowcast"
    nowcast_cache_dir = settings.tile_dir / "cache" / "nowcast"
    shutil.rmtree(nowcast_src_dir, ignore_errors=True)
    shutil.rmtree(nowcast_cache_dir, ignore_errors=True)

    valid_times: list[datetime] = []
    for valid_time, field in predicted:
        dest = _source_path(settings, "nowcast", valid_time, ".h5")
        write_mosaic(dest, field, seed=seed, timestamp=valid_time)
        valid_times.append(valid_time)

    replace_layer_frames(
        manifest, "nowcast",
        timestamps=valid_times,
        tile_url_template="nowcast/{timestamp}/{z}/{x}/{y}.png",
        min_zoom=settings.min_zoom,
        max_zoom=settings.max_zoom,
    )
    touch_generated_at(manifest)
    write_manifest(manifest_path, manifest)
    log.info(
        "nowcast.frames.saved",
        count=len(valid_times),
        base=seed.timestamp.isoformat(),
    )


# ----- maintenance --------------------------------------------------------


@app.command()
def cleanup() -> None:
    """Delete sources + cached tiles older than the retention window, and trim the manifest."""
    from .retention import cleanup_layer_v2

    settings = get_settings()
    manifest_path = settings.tile_dir / "manifest.json"
    if not manifest_path.exists():
        typer.echo(f"no manifest at {manifest_path}; nothing to clean")
        return
    manifest = read_manifest(manifest_path)
    total = 0
    for layer in ("radar", "nowcast", "forecast"):
        total += cleanup_layer_v2(
            tile_dir=settings.tile_dir,
            layer=layer,
            max_age_hours=settings.retention_hours,
            manifest=manifest,
        )
    touch_generated_at(manifest)
    write_manifest(manifest_path, manifest)
    typer.echo(f"removed {total} stale frames")


@app.command("init-manifest")
def init_manifest() -> None:
    """Write a fresh empty manifest at the configured tile dir."""
    settings = get_settings()
    bbox = {
        "latMin": settings.bbox.lat_min, "latMax": settings.bbox.lat_max,
        "lonMin": settings.bbox.lon_min, "lonMax": settings.bbox.lon_max,
    }
    manifest = empty_manifest(bbox=bbox, color_scale=settings.color_scale)
    target = settings.tile_dir / "manifest.json"
    write_manifest(target, manifest)
    typer.echo(f"wrote empty manifest at {target}")


@app.command("validate-manifest")
def validate_manifest_cmd(path: Path) -> None:
    """Validate a manifest file against the JSON schema."""
    read_manifest(path)
    typer.echo(f"{path}: OK")


# ----- tile server --------------------------------------------------------


@app.command("tile-server")
def tile_server_cmd(
    host: str | None = typer.Option(None, help="Override RADAR_TILE_SERVER_HOST"),
    port: int | None = typer.Option(None, help="Override RADAR_TILE_SERVER_PORT"),
) -> None:
    """Run the lazy tile-rendering HTTP server (uvicorn)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "radar.tile_server:app",
        host=host or settings.tile_server_host,
        port=port or settings.tile_server_port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    app()
