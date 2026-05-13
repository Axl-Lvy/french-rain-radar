"""Reproject Lambert-93 (EPSG:2154) grids to Web Mercator (EPSG:3857).

The bounding box and output tile size are fixed at configuration time, so the
reprojection mapping is computed once and reused for every frame. This avoids
pulling in rasterio/GDAL.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import Transformer

from .config import Bbox

# Web Mercator extent for a lon/lat point.
_TO_WEBMERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_FROM_WEBMERCATOR = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class ReprojectionGrid:
    """Pre-computed pixel→source-grid mapping for a fixed bbox + output size."""

    width: int
    height: int
    # For each output pixel (row, col), the corresponding (row, col) in the source array,
    # as floats so we can bilinearly interpolate.
    src_rows: np.ndarray
    src_cols: np.ndarray


def build_grid(
    bbox: Bbox,
    *,
    width: int,
    height: int,
    src_lats: np.ndarray,
    src_lons: np.ndarray,
) -> ReprojectionGrid:
    """Compute the reprojection grid once at startup.

    Args:
        bbox: target bounding box in lat/lon.
        width / height: output PNG dimensions in pixels.
        src_lats / src_lons: 1-D arrays describing the source grid's coordinate axes
            (assumed regular). For non-regular source grids, swap in a KD-tree lookup.

    Returns:
        ReprojectionGrid usable by :func:`resample`.
    """
    # Build output pixel centers in Web Mercator, then convert back to lat/lon.
    x_min, y_min = _TO_WEBMERCATOR.transform(bbox.lon_min, bbox.lat_min)
    x_max, y_max = _TO_WEBMERCATOR.transform(bbox.lon_max, bbox.lat_max)
    xs = np.linspace(x_min, x_max, width)
    ys = np.linspace(y_max, y_min, height)  # top to bottom for image coords
    xv, yv = np.meshgrid(xs, ys)
    lons, lats = _FROM_WEBMERCATOR.transform(xv, yv)

    src_cols = np.interp(lons, src_lons, np.arange(src_lons.size))
    src_rows = np.interp(lats, src_lats, np.arange(src_lats.size))
    return ReprojectionGrid(width=width, height=height, src_rows=src_rows, src_cols=src_cols)


def resample(values: np.ndarray, grid: ReprojectionGrid) -> np.ndarray:
    """Bilinear-sample ``values`` onto ``grid``. Returns array of shape (height, width)."""
    from scipy.ndimage import map_coordinates

    return map_coordinates(
        values,
        np.stack([grid.src_rows, grid.src_cols]),
        order=1,
        mode="constant",
        cval=np.nan,
    )
