"""Read/write an ODIM_H5 (V2_3) Météo-France radar mosaic.

These files are served by the DPRadar API at maille=500 (HDF5). Format reference:
<https://www.eumetnet.eu/wp-content/uploads/2017/01/OPERA_hdf_description_2014.pdf>

The DPRadar METROPOLE LAME_D_EAU product carries a 3472x3472 grid of 5-minute
precipitation accumulations in a polar-stereographic projection. The PROJ
definition lives at ``/where/projdef``; data lives at
``/dataset1/data1/data`` with ``gain``/``offset``/``nodata``/``undetect``
attributes on ``/dataset1/data1/what``.

The :func:`write_mosaic` helper produces files in a compatible layout — used
by ``radar nowcast`` to persist extrapolated frames alongside observed ones,
so the tile server's existing ``.h5`` code path renders both transparently.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import h5py
import numpy as np


@dataclass(frozen=True)
class RadarMosaic:
    """One radar mosaic frame in its native polar-stereographic grid.

    ``values`` holds 5-minute precipitation accumulation in mm (NaN for
    nodata / undetect cells).
    """

    values: np.ndarray          # shape (ysize, xsize), float32, mm of water
    timestamp: datetime         # UTC end-time of the 5-min accumulation window
    proj_def: str               # PROJ string describing the source grid CRS
    x_scale: float              # metres per pixel along the X axis
    y_scale: float              # metres per pixel along the Y axis
    # Corner lon/lat of the four mosaic corners (degrees, WGS84)
    ul_lon: float
    ul_lat: float
    ur_lon: float
    ur_lat: float
    ll_lon: float
    ll_lat: float
    lr_lon: float
    lr_lat: float


def read_mosaic(path: Path) -> RadarMosaic:
    """Parse the file at ``path`` and return one ``RadarMosaic``."""
    with h5py.File(path, "r") as f:
        where = f["/where"].attrs
        what_root = f["/dataset1/what"].attrs
        what_data = f["/dataset1/data1/what"].attrs
        raw = f["/dataset1/data1/data"][()]

        gain = float(what_data["gain"])
        offset = float(what_data["offset"])
        nodata = float(what_data["nodata"])
        undetect = float(what_data["undetect"])

        values = raw.astype(np.float32) * np.float32(gain) + np.float32(offset)
        # Mark missing as NaN AFTER scaling
        mask = (raw == nodata) | (raw == undetect)
        values[mask] = np.nan

        # End-of-window timestamp (e.g. enddate=20260513, endtime=204500 → 20:45:00 UTC)
        enddate = what_root["enddate"].decode()
        endtime = what_root["endtime"].decode()
        timestamp = datetime.strptime(enddate + endtime, "%Y%m%d%H%M%S").replace(
            tzinfo=UTC
        )

        return RadarMosaic(
            values=values,
            timestamp=timestamp,
            proj_def=where["projdef"].decode().strip(),
            x_scale=float(where["xscale"]),
            y_scale=float(where["yscale"]),
            ul_lon=float(where["UL_lon"]),
            ul_lat=float(where["UL_lat"]),
            ur_lon=float(where["UR_lon"]),
            ur_lat=float(where["UR_lat"]),
            ll_lon=float(where["LL_lon"]),
            ll_lat=float(where["LL_lat"]),
            lr_lon=float(where["LR_lon"]),
            lr_lat=float(where["LR_lat"]),
        )


def mm_per_window_to_mm_per_hour(window_minutes: int = 5) -> float:
    """Multiplier to convert mm accumulated over a window to mm/h.

    DPRadar LAME_D_EAU uses a 5-min window: 60 / 5 = 12.
    """
    if window_minutes <= 0:
        raise ValueError("window_minutes must be positive")
    return 60.0 / window_minutes


def write_mosaic(
    path: Path,
    mm_window: np.ndarray,
    *,
    seed: RadarMosaic,
    timestamp: datetime,
    gain: float = 0.01,
    offset: float = 0.0,
    nodata: int = 65535,
    undetect: int = 0,
) -> None:
    """Write ``mm_window`` to ``path`` in the same ODIM_H5 layout :func:`read_mosaic` consumes.

    Projection metadata (CRS, scales, corner lon/lats) is copied from ``seed``;
    ``timestamp`` becomes the end-of-window time. NaN cells are stored as the
    ``nodata`` sentinel; finite values are encoded as
    ``round((value - offset) / gain)`` clipped to uint16.

    Atomic + mode 0644 so Caddy / the tile-server user can read what the
    nowcast writer produces.
    """
    if mm_window.ndim != 2:
        raise ValueError(f"mm_window must be 2-D, got shape {mm_window.shape}")

    mask = np.isnan(mm_window)
    scaled = np.where(mask, 0.0, (mm_window - offset) / gain)
    raw = np.clip(np.round(scaled), 0, 65534).astype(np.uint16)
    raw = np.where(mask, np.uint16(nodata), raw)

    ts_utc = timestamp.astimezone(UTC)
    enddate = ts_utc.strftime("%Y%m%d")
    endtime = ts_utc.strftime("%H%M%S")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmp_str)
    try:
        with h5py.File(tmp, "w") as f:
            where = f.create_group("/where")
            where.attrs["projdef"] = np.bytes_(seed.proj_def)
            where.attrs["xscale"] = float(seed.x_scale)
            where.attrs["yscale"] = float(seed.y_scale)
            where.attrs["UL_lon"] = float(seed.ul_lon)
            where.attrs["UL_lat"] = float(seed.ul_lat)
            where.attrs["UR_lon"] = float(seed.ur_lon)
            where.attrs["UR_lat"] = float(seed.ur_lat)
            where.attrs["LL_lon"] = float(seed.ll_lon)
            where.attrs["LL_lat"] = float(seed.ll_lat)
            where.attrs["LR_lon"] = float(seed.lr_lon)
            where.attrs["LR_lat"] = float(seed.lr_lat)

            what_root = f.create_group("/dataset1/what")
            what_root.attrs["enddate"] = np.bytes_(enddate)
            what_root.attrs["endtime"] = np.bytes_(endtime)

            what_data = f.create_group("/dataset1/data1/what")
            what_data.attrs["gain"] = float(gain)
            what_data.attrs["offset"] = float(offset)
            what_data.attrs["nodata"] = float(nodata)
            what_data.attrs["undetect"] = float(undetect)

            f.create_dataset("/dataset1/data1/data", data=raw, compression="gzip")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
