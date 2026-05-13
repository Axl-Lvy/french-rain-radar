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
    """Download the latest AROME-PI run (24 lead-time GRIBs) and update manifest."""
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
        if existing_run == run_iso:
            log.info("arome.skip.same-run", run=run_iso)
            return

        # Fetch all 24 leadtime GRIBs into the per-run source dir.
        valid_times: list[datetime] = []
        for forecast in mf.fetch_arome_run(
            latest_run,
            bbox=_bbox_tuple(settings.bbox),
            dest_dir=settings.tile_dir / "sources" / "forecast",
            lead_times_s=AROME_LEAD_TIMES_S,
        ):
            # Rename to the URL-safe pattern so tile server can find it.
            target = _source_path(settings, "forecast", forecast.valid_time, ".grib2")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target != forecast.path:
                forecast.path.rename(target)
            valid_times.append(forecast.valid_time)

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

    Requires the optional ``nowcast`` extra (pysteps). Not yet implemented.
    """
    typer.echo("TODO: implement pysteps extrapolation (Phase 1 follow-up)")


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
