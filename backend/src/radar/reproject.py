"""Reproject native source grids to Web Mercator (EPSG:3857) for client overlays.

Two source-grid shapes are supported, each with its own builder:

- :func:`build_grid` — regular lat/lon source (used by AROME-PI's WCS subset,
  which already returns the data on an EPSG:4326 grid).
- :func:`build_proj_grid` — a regular grid in an arbitrary PROJ-defined CRS,
  with known origin + scales (used by the ODIM_H5 radar mosaic at 500 m in
  polar stereographic).

Both produce a :class:`ReprojectionGrid` that :func:`resample` consumes. The
mapping is computed once at startup and re-used for every frame.
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


def build_proj_grid(
    bbox: Bbox,
    *,
    width: int,
    height: int,
    src_crs: str,
    src_origin_x: float,
    src_origin_y: float,
    src_xscale: float,
    src_yscale: float,
    src_shape: tuple[int, int],  # (rows, cols)
) -> ReprojectionGrid:
    """Reprojection grid for a regular source grid defined in a projected CRS.

    The source grid is assumed pixel-aligned to ``src_origin_x``/``src_origin_y``
    (upper-left corner, in the source CRS metres), with positive ``src_xscale``
    going right and positive ``src_yscale`` going down (image convention).

    Args:
        bbox: target bbox in WGS84 lat/lon.
        width / height: output PNG dimensions in pixels.
        src_crs: PROJ string describing the source CRS (e.g. the ODIM_H5
            ``/where/projdef`` attribute).
        src_origin_x / src_origin_y: source CRS metres at the source grid's
            upper-left pixel (column 0, row 0).
        src_xscale: metres per pixel along the source grid's columns axis.
        src_yscale: metres per pixel along the source grid's rows axis.
        src_shape: (nrows, ncols) of the source grid; used to clip out-of-bounds
            samples so they don't accidentally wrap.
    """
    x_min, y_min = _TO_WEBMERCATOR.transform(bbox.lon_min, bbox.lat_min)
    x_max, y_max = _TO_WEBMERCATOR.transform(bbox.lon_max, bbox.lat_max)
    xs = np.linspace(x_min, x_max, width)
    ys = np.linspace(y_max, y_min, height)
    xv, yv = np.meshgrid(xs, ys)
    lons, lats = _FROM_WEBMERCATOR.transform(xv, yv)

    # WGS84 lat/lon -> source CRS metres.
    to_src = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
    src_x, src_y = to_src.transform(lons, lats)
    src_cols = (src_x - src_origin_x) / src_xscale
    src_rows = (src_origin_y - src_y) / src_yscale
    # Clamp out-of-bounds to NaN-producing index (-1) so resample marks them missing.
    nrows, ncols = src_shape
    oob = (src_cols < 0) | (src_cols > ncols - 1) | (src_rows < 0) | (src_rows > nrows - 1)
    src_cols = np.where(oob, -1.0, src_cols)
    src_rows = np.where(oob, -1.0, src_rows)
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
