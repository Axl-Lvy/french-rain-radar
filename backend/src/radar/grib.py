"""GRIB2 reading helpers around xarray + cfgrib."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import structlog
import xarray as xr

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PrecipField:
    """A single observed-or-forecast 2-D precipitation grid in its native projection."""

    values: np.ndarray  # shape (h, w), mm/h
    lats: np.ndarray    # native-grid latitudes (1-D or 2-D)
    lons: np.ndarray    # native-grid longitudes (1-D or 2-D)
    timestamp: datetime  # UTC observation or valid time


def open_grib(path: Path) -> xr.Dataset:
    """Open a GRIB2 file with cfgrib."""
    return xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})


def read_precip(path: Path) -> PrecipField:
    """Read a precipitation field (mm/h) from a Météo-France GRIB2 file.

    TODO: confirm the variable name used in the radar mosaic and AROME-NWC GRIBs
    (`tp`, `pre`, `mxtpr`, ...) and normalise units.
    """
    raise NotImplementedError("TODO: implement against an actual sample GRIB")
