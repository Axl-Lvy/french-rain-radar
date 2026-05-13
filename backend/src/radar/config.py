"""Runtime configuration, sourced from environment variables.

Loaded by systemd from /etc/radar/env in production. In dev you can either
export the variables or rely on the defaults below (which point at the local
tree under dev/data/).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Bbox(BaseSettings):
    """Geographic bounding box rendered into every tile pyramid.

    Defaults cover metropolitan France including Corsica. Override via the envs
    ``RADAR_BBOX_LAT_MIN`` / ``LAT_MAX`` / ``LON_MIN`` / ``LON_MAX``.
    """

    model_config = SettingsConfigDict(env_prefix="RADAR_BBOX_", extra="ignore")

    lat_min: float = 41.3
    lat_max: float = 51.5
    lon_min: float = -5.5
    lon_max: float = 10.0


class Settings(BaseSettings):
    """Top-level pipeline configuration."""

    model_config = SettingsConfigDict(env_prefix="RADAR_", extra="ignore", env_file=None)

    # Météo-France issues one API key per subscription. We use two APIs
    # (AROME-PI for forecast, Radar for observation), so two tokens. If your
    # portal application is subscribed to both APIs, the same string works
    # for both — just set both variables to the same value.
    meteofrance_token_arome: str = Field(default="", validation_alias="METEOFRANCE_TOKEN_AROME")
    meteofrance_token_radar: str = Field(default="", validation_alias="METEOFRANCE_TOKEN_RADAR")

    # Disk roots. ``tile_dir`` holds the public-facing files:
    #   <tile_dir>/manifest.json    (read by clients)
    #   <tile_dir>/cache/<layer>/<ts>/<z>/<x>/<y>.png   (rendered tiles served by Caddy)
    # Cached source GRIB / HDF5 files (private; read by the tile server) live at:
    #   <tile_dir>/sources/<layer>/<ts>.{grib2,h5}
    tile_dir: Path = Path("dev/data/tiles")

    retention_hours: int = 12
    color_scale: str = "rainviewer-original"
    log_level: str = "INFO"

    # XYZ zoom range advertised to clients. The tile server can render any zoom
    # the client asks for, but past max_zoom the underlying source resolution
    # is exhausted (radar is ~500 m → z=11 saturates).
    min_zoom: int = 5
    max_zoom: int = 10

    # Tile-renderer HTTP service.
    tile_server_host: str = "127.0.0.1"
    tile_server_port: int = 8765

    # Which pysteps method `radar nowcast` runs. "extrapolation" = LK +
    # semi-Lagrangian advection (default, cheap); "sprog" = LK + AR(2)
    # cascade (better 30-60 min skill, heavier FFT cost per step).
    nowcast_method: Literal["extrapolation", "sprog"] = "extrapolation"

    bbox: Bbox = Field(default_factory=Bbox)


def get_settings() -> Settings:
    """Build a `Settings` from the current environment (cached at module level in callers)."""
    return Settings()
