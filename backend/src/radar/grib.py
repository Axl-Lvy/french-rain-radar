"""GRIB2 reading helpers around xarray + cfgrib.

Used for AROME-PI lead-time GRIB files. The variable cfgrib decodes as
``tirf`` ("Time integral of rain flux"), unit kg/m² over a 15-min accumulation
window. We convert to mm/h on read (kg/m² for 15 min -> mm in 15 min -> mm/h x 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
    """Open a GRIB2 file with cfgrib. ``indexpath=""`` disables the on-disk index file."""
    return xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})


def read_arome_pi_precip(path: Path) -> PrecipField:
    """Read one AROME-PI lead-time GRIB and return the 15-min accumulation as mm/h.

    The GRIB carries the cumulative rain over the 15-min window in kg/m² (= mm of
    water). We multiply by 4 to express it as mm/h, which is what the
    colormap / nowcast / client all expect.
    """
    with open_grib(path) as ds:
        if "tirf" not in ds.data_vars:
            raise RuntimeError(
                f"AROME-PI GRIB does not expose 'tirf'; vars={list(ds.data_vars)}"
            )

        values_mm_15min = ds["tirf"].values.astype(np.float32)
        values_mm_h = values_mm_15min * np.float32(4.0)

        lats = ds["latitude"].values.astype(np.float64)
        lons = ds["longitude"].values.astype(np.float64)

        # cfgrib exposes valid_time as a scalar datetime64.
        valid_time = ds.coords.get("valid_time")
        if valid_time is None:
            raise RuntimeError("AROME-PI GRIB missing valid_time coord")
        ts = np.datetime64(valid_time.values).astype("datetime64[s]").astype(int)
        timestamp = datetime.fromtimestamp(ts, tz=UTC)

    return PrecipField(values=values_mm_h, lats=lats, lons=lons, timestamp=timestamp)


# Kept as the public name for both observed and forecast precip readers.
def read_precip(path: Path) -> PrecipField:
    """Read a precipitation field (mm/h) from an AROME-PI GRIB2 file.

    For ODIM_H5 radar mosaics, use :func:`radar.radar_hdf5.read_mosaic` instead;
    its native grid (polar stereographic 500 m) is structurally different.
    """
    return read_arome_pi_precip(path)
