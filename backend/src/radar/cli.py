"""Command-line entry point. Each subcommand is what its matching systemd timer calls."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog
import typer

from . import __version__
from .config import get_settings
from .manifest import empty_manifest, read_manifest, write_manifest

app = typer.Typer(help="French rain radar pipeline.", add_completion=False)


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


@app.command("ingest-radar")
def ingest_radar() -> None:
    """Fetch the latest radar mosaic, render PNG, update manifest."""
    raise typer.Exit(typer.echo("TODO: implement ingest-radar"))


@app.command("nowcast")
def nowcast() -> None:
    """Run pysteps optical-flow extrapolation on the latest radar frames."""
    raise typer.Exit(typer.echo("TODO: implement nowcast"))


@app.command("ingest-arome")
def ingest_arome() -> None:
    """Fetch the latest AROME-NWC run and render forecast PNGs."""
    raise typer.Exit(typer.echo("TODO: implement ingest-arome"))


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
