"""XYZ tile geometry + per-tile rendering helpers.

The tile server calls into here on every cache-miss to produce one 256x256
PNG covering the requested (z, x, y) tile, sampling from a cached source
field (AROME-PI GRIB on a regular lat/lon grid, or DPRadar HDF5 on a
polar-stereographic grid).
"""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates

from .colormap import colorize

# Shared transformers (thread-safe).
_LL_TO_MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_MERCATOR_TO_LL = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

TILE_SIZE = 256


def tile_lonlat_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Return (lon_min, lat_min, lon_max, lat_max) in degrees for tile (z, x, y)."""
    n = 2**z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lon_min, lat_min, lon_max, lat_max


def _tile_mercator_pixel_grid(z: int, x: int, y: int) -> tuple[np.ndarray, np.ndarray]:
    """Return ``TILE_SIZE x TILE_SIZE`` lat/lon arrays for each pixel of the tile.

    Pixel order matches image convention: row 0 = north, column 0 = west.
    """
    lon_min, lat_min, lon_max, lat_max = tile_lonlat_bbox(z, x, y)
    x_min_m, y_min_m = _LL_TO_MERCATOR.transform(lon_min, lat_min)
    x_max_m, y_max_m = _LL_TO_MERCATOR.transform(lon_max, lat_max)
    xs = np.linspace(x_min_m, x_max_m, TILE_SIZE)
    ys = np.linspace(y_max_m, y_min_m, TILE_SIZE)  # north (top) first
    xv, yv = np.meshgrid(xs, ys)
    lons, lats = _MERCATOR_TO_LL.transform(xv, yv)
    return lats, lons


def _png_bytes(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def render_tile_lonlat(
    *,
    values: np.ndarray,       # source field, mm/h, shape (H, W)
    src_lats: np.ndarray,     # 1-D, length H
    src_lons: np.ndarray,     # 1-D, length W
    z: int,
    x: int,
    y: int,
    color_scale: str,
) -> bytes:
    """Render a 256x256 tile from a regular lat/lon source field."""
    lats, lons = _tile_mercator_pixel_grid(z, x, y)

    # Source axes may be increasing or decreasing in latitude.
    if src_lats[0] > src_lats[-1]:
        flipped_lats = src_lats[::-1]
        flipped_values = values[::-1, :]
    else:
        flipped_lats = src_lats
        flipped_values = values

    src_cols = np.interp(lons, src_lons, np.arange(src_lons.size))
    src_rows = np.interp(lats, flipped_lats, np.arange(flipped_lats.size))
    sampled = map_coordinates(
        flipped_values, np.stack([src_rows, src_cols]),
        order=1, mode="constant", cval=np.nan,
    )
    rgba = colorize(sampled, scale=color_scale)
    return _png_bytes(rgba)


def render_tile_projected(
    *,
    values: np.ndarray,         # source field, mm/h, shape (rows, cols)
    src_crs: str,               # PROJ string of the source grid CRS
    src_origin_x: float,        # metres in src_crs at source (col=0, row=0) corner
    src_origin_y: float,
    src_xscale: float,          # metres per source pixel along columns
    src_yscale: float,          # metres per source pixel along rows (positive, image-down)
    z: int,
    x: int,
    y: int,
    color_scale: str,
) -> bytes:
    """Render a 256x256 tile from a regular projected source grid (e.g. radar PS)."""
    lats, lons = _tile_mercator_pixel_grid(z, x, y)

    to_src = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
    src_x_arr, src_y_arr = to_src.transform(lons, lats)
    src_cols = (src_x_arr - src_origin_x) / src_xscale
    src_rows = (src_origin_y - src_y_arr) / src_yscale

    nrows, ncols = values.shape
    oob = (src_cols < 0) | (src_cols > ncols - 1) | (src_rows < 0) | (src_rows > nrows - 1)
    src_cols = np.where(oob, -1.0, src_cols)
    src_rows = np.where(oob, -1.0, src_rows)

    sampled = map_coordinates(
        values, np.stack([src_rows, src_cols]),
        order=1, mode="constant", cval=np.nan,
    )
    rgba = colorize(sampled, scale=color_scale)
    return _png_bytes(rgba)
