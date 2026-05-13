"""Runtime configuration, sourced from environment variables.

Loaded by systemd from /etc/radar/env in production. In dev you can either
export the variables or rely on the defaults below (which point at the local
tree under dev/data/tiles).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Bbox(BaseSettings):
    """Geographic bounding box rendered into every tile."""

    model_config = SettingsConfigDict(env_prefix="RADAR_BBOX_", extra="ignore")

    lat_min: float = 43.6
    lat_max: float = 44.2
    lon_min: float = 4.6
    lon_max: float = 5.6


class Settings(BaseSettings):
    """Top-level pipeline configuration."""

    model_config = SettingsConfigDict(env_prefix="RADAR_", extra="ignore", env_file=None)

    # Météo-France issues one API key per subscription. We use two APIs
    # (AROME-PI for forecast, Radar for observation), so two tokens. If your
    # portal application is subscribed to both APIs, the same string works
    # for both — just set both variables to the same value.
    meteofrance_token_arome: str = Field(default="", validation_alias="METEOFRANCE_TOKEN_AROME")
    meteofrance_token_radar: str = Field(default="", validation_alias="METEOFRANCE_TOKEN_RADAR")
    tile_dir: Path = Path("dev/data/tiles")
    retention_hours: int = 12
    tile_width: int = 512
    tile_height: int = 384
    color_scale: str = "rainviewer-original"
    log_level: str = "INFO"

    bbox: Bbox = Field(default_factory=Bbox)


def get_settings() -> Settings:
    """Build a `Settings` from the current environment (cached at module level in callers)."""
    return Settings()
