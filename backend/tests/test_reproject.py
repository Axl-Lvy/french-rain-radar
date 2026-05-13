"""Tests for the reprojection grid."""

from __future__ import annotations

import numpy as np

from radar.config import Bbox
from radar.reproject import build_grid, resample


def test_grid_shape() -> None:
    bbox = Bbox(lat_min=43.6, lat_max=44.2, lon_min=4.6, lon_max=5.6)
    src_lats = np.linspace(43.0, 45.0, 200)
    src_lons = np.linspace(4.0, 6.0, 200)
    grid = build_grid(bbox, width=512, height=384, src_lats=src_lats, src_lons=src_lons)
    assert grid.src_rows.shape == (384, 512)
    assert grid.src_cols.shape == (384, 512)


def test_resample_constant_field() -> None:
    bbox = Bbox(lat_min=43.6, lat_max=44.2, lon_min=4.6, lon_max=5.6)
    src_lats = np.linspace(43.0, 45.0, 200)
    src_lons = np.linspace(4.0, 6.0, 200)
    grid = build_grid(bbox, width=64, height=48, src_lats=src_lats, src_lons=src_lons)
    src = np.full((200, 200), 3.5, dtype=np.float32)
    out = resample(src, grid)
    assert np.allclose(out, 3.5, atol=1e-3)
