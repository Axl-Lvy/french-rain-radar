"""Command-line entry point. Each subcommand is what its matching systemd timer calls."""

from __future__ import annotations

import logging
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
import typer

from . import __version__
from .config import Bbox, Settings, get_settings
from .manifest import (
    empty_manifest,
    most_recent_timestamp,
    read_manifest,
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


def _bbox_tuple(b: Bbox) -> tuple[float, float, float, float]:
    """Return (lon_min, lat_min, lon_max, lat_max) for the WCS subset convention."""
    return (b.lon_min, b.lat_min, b.lon_max, b.lat_max)


def _png_filename(ts: datetime) -> str:
    """File-system-safe ISO timestamp (no colons)."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ.png")


def _load_or_init_manifest(settings: Settings) -> tuple[Path, dict]:
    manifest_path = settings.tile_dir / "manifest.json"
    if manifest_path.exists():
        return manifest_path, read_manifest(manifest_path)
    bbox = {
        "latMin": settings.bbox.lat_min, "latMax": settings.bbox.lat_max,
        "lonMin": settings.bbox.lon_min, "lonMax": settings.bbox.lon_max,
    }
    tile_size = {"width": settings.tile_width, "height": settings.tile_height}
    return manifest_path, empty_manifest(
        bbox=bbox, tile_size=tile_size, color_scale=settings.color_scale,
    )


def _replace_frames(manifest: dict, layer: str, frames: list[dict]) -> None:
    manifest["layers"].setdefault(layer, {"frames": []})["frames"] = sorted(
        frames, key=lambda f: f["timestamp"]
    )
    manifest["generatedAt"] = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )


@app.command("ingest-radar")
def ingest_radar() -> None:
    """Fetch the latest radar mosaic, render PNG, update manifest.

    Idempotent: if Météo-France's latest frame is the one already in the
    manifest, this exits without downloading the payload.
    """
    from .colormap import colorize
    from .manifest import write_manifest
    from .meteofrance import MeteoFranceClient
    from .radar_hdf5 import mm_per_window_to_mm_per_hour, read_mosaic
    from .render import write_png
    from .reproject import build_proj_grid, resample

    settings = get_settings()
    manifest_path, manifest = _load_or_init_manifest(settings)
    known_latest = most_recent_timestamp(manifest, "radar")

    with MeteoFranceClient(
        arome_token=settings.meteofrance_token_arome,
        radar_token=settings.meteofrance_token_radar,
    ) as mf:
        new_validity = mf.latest_radar_validity()
        if new_validity is None:
            log.warning("radar descriptor has no validity_time; skipping")
            return
        if known_latest and new_validity <= known_latest:
            log.info("radar.skip.same-validity", validity=new_validity.isoformat())
            return

        # Heavy fetch (HDF5, ~2 MB).
        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            frame = mf.fetch_latest_radar(dest=tmp_path)
            mosaic = read_mosaic(frame.path)
        finally:
            tmp_path.unlink(missing_ok=True)

    # Source-grid origin in projected metres = projected UL corner.
    from pyproj import Transformer
    to_src = Transformer.from_crs("EPSG:4326", mosaic.proj_def, always_xy=True)
    ul_x, ul_y = to_src.transform(mosaic.ul_lon, mosaic.ul_lat)

    grid = build_proj_grid(
        settings.bbox,
        width=settings.tile_width,
        height=settings.tile_height,
        src_crs=mosaic.proj_def,
        src_origin_x=ul_x,
        src_origin_y=ul_y,
        src_xscale=mosaic.x_scale,
        src_yscale=mosaic.y_scale,
        src_shape=mosaic.values.shape,
    )
    mm_h = resample(mosaic.values * mm_per_window_to_mm_per_hour(5), grid)
    rgba = colorize(mm_h, scale=settings.color_scale)

    png_rel = f"radar/{_png_filename(mosaic.timestamp)}"
    png_abs = settings.tile_dir / png_rel
    write_png(rgba, png_abs)

    existing = [f for f in manifest["layers"].get("radar", {}).get("frames", [])
                if f["url"] != png_rel]
    existing.append({
        "timestamp": mosaic.timestamp.isoformat().replace("+00:00", "Z"),
        "url": png_rel,
    })
    _replace_frames(manifest, "radar", existing)
    write_manifest(manifest_path, manifest)
    log.info("radar.frame.written", validity=mosaic.timestamp.isoformat(), url=png_rel)


@app.command("nowcast")
def nowcast() -> None:
    """Run pysteps optical-flow extrapolation on the latest radar frames.

    No network call. Requires the optional ``nowcast`` extra (pysteps).
    """
    typer.echo("TODO: implement pysteps extrapolation in a follow-up commit")


@app.command("ingest-arome")
def ingest_arome() -> None:
    """Fetch the latest AROME-PI run and render its 24 lead-time forecast PNGs.

    Idempotent against the run reference time.
    """
    from .colormap import colorize
    from .grib import read_precip
    from .manifest import write_manifest
    from .meteofrance import AROME_LEAD_TIMES_S, MeteoFranceClient
    from .render import write_png
    from .reproject import build_grid, resample

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
        existing_run = manifest["layers"].get("forecast", {}).get("runTime")
        if existing_run == run_iso:
            log.info("arome.skip.same-run", run=run_iso)
            return

        new_frames: list[dict] = []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for forecast in mf.fetch_arome_run(
                latest_run,
                bbox=_bbox_tuple(settings.bbox),
                dest_dir=tmp,
                lead_times_s=AROME_LEAD_TIMES_S,
            ):
                field = read_precip(forecast.path)
                # AROME-PI is already on a regular lat/lon grid; use the simple builder.
                grid = build_grid(
                    settings.bbox,
                    width=settings.tile_width,
                    height=settings.tile_height,
                    src_lats=field.lats[::-1] if field.lats[0] > field.lats[-1] else field.lats,
                    src_lons=field.lons,
                )
                values = field.values[::-1] if field.lats[0] > field.lats[-1] else field.values
                mm_h = resample(values, grid)
                rgba = colorize(mm_h, scale=settings.color_scale)
                png_rel = f"forecast/{_png_filename(forecast.valid_time)}"
                write_png(rgba, settings.tile_dir / png_rel)
                new_frames.append({
                    "timestamp": forecast.valid_time.isoformat().replace("+00:00", "Z"),
                    "url": png_rel,
                })

    _replace_frames(manifest, "forecast", new_frames)
    manifest["layers"]["forecast"]["runTime"] = run_iso
    write_manifest(manifest_path, manifest)
    log.info("arome.run.written", run=run_iso, frames=len(new_frames))


@app.command()
def cleanup() -> None:
    """Delete frames older than the retention window."""
    from datetime import timedelta

    from .retention import cleanup_layer

    settings = get_settings()
    manifest_path = settings.tile_dir / "manifest.json"
    if not manifest_path.exists():
        typer.echo(f"no manifest at {manifest_path}; nothing to clean")
        return
    manifest = read_manifest(manifest_path)
    max_age = timedelta(hours=settings.retention_hours)
    total = sum(cleanup_layer(settings.tile_dir, layer, max_age, manifest)
                for layer in ("radar", "nowcast", "forecast"))
    write_manifest(manifest_path, manifest)
    typer.echo(f"removed {total} stale frames")


@app.command("init-manifest")
def init_manifest() -> None:
    """Write an empty, valid manifest at the configured tile dir."""
    settings = get_settings()
    bbox = {
        "latMin": settings.bbox.lat_min, "latMax": settings.bbox.lat_max,
        "lonMin": settings.bbox.lon_min, "lonMax": settings.bbox.lon_max,
    }
    tile_size = {"width": settings.tile_width, "height": settings.tile_height}
    manifest = empty_manifest(bbox=bbox, tile_size=tile_size, color_scale=settings.color_scale)
    target = settings.tile_dir / "manifest.json"
    write_manifest(target, manifest)
    typer.echo(f"wrote empty manifest at {target}")


@app.command("validate-manifest")
def validate_manifest_cmd(path: Path) -> None:
    """Validate a manifest file against the JSON schema."""
    read_manifest(path)  # raises on invalid
    typer.echo(f"{path}: OK")


if __name__ == "__main__":
    app()
