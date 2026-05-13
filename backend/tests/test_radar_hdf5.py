"""Tests for the ODIM_H5 reader/writer pair."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from radar.radar_hdf5 import RadarMosaic, downsample_mosaic, read_mosaic, write_mosaic

_SEED = RadarMosaic(
    values=np.zeros((6, 8), dtype=np.float32),
    timestamp=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    proj_def="+proj=stere +lat_0=45 +lon_0=0 +R=6371229",
    x_scale=500.0, y_scale=500.0,
    ul_lon=-5.5, ul_lat=51.5,
    ur_lon=10.0, ur_lat=51.5,
    ll_lon=-5.5, ll_lat=41.3,
    lr_lon=10.0, lr_lat=41.3,
)


def test_write_then_read_preserves_metadata(tmp_path: Path) -> None:
    values = np.full((6, 8), 1.25, dtype=np.float32)
    ts = datetime(2026, 5, 13, 12, 35, tzinfo=UTC)
    dest = tmp_path / "frame.h5"

    write_mosaic(dest, values, seed=_SEED, timestamp=ts)
    out = read_mosaic(dest)

    assert out.timestamp == ts
    assert out.proj_def == _SEED.proj_def
    assert out.x_scale == _SEED.x_scale
    assert out.ul_lon == _SEED.ul_lon
    assert out.lr_lat == _SEED.lr_lat


def test_write_then_read_preserves_values_within_gain_precision(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    values = rng.uniform(0.0, 50.0, size=(6, 8)).astype(np.float32)
    ts = datetime(2026, 5, 13, 13, 0, tzinfo=UTC)
    dest = tmp_path / "frame.h5"

    write_mosaic(dest, values, seed=_SEED, timestamp=ts, gain=0.01)
    out = read_mosaic(dest)

    np.testing.assert_allclose(out.values, values, atol=0.01)


def test_write_encodes_nan_as_nodata(tmp_path: Path) -> None:
    values = np.ones((6, 8), dtype=np.float32)
    values[2, 3] = np.nan
    values[5, 7] = np.nan
    dest = tmp_path / "frame.h5"

    write_mosaic(dest, values, seed=_SEED, timestamp=_SEED.timestamp)
    out = read_mosaic(dest)

    assert np.isnan(out.values[2, 3])
    assert np.isnan(out.values[5, 7])
    finite = ~np.isnan(values)
    np.testing.assert_allclose(out.values[finite], values[finite], atol=0.01)


def test_write_chmods_to_0644(tmp_path: Path) -> None:
    dest = tmp_path / "frame.h5"
    write_mosaic(dest, np.zeros((6, 8), dtype=np.float32), seed=_SEED, timestamp=_SEED.timestamp)
    assert (dest.stat().st_mode & 0o777) == 0o644


def test_downsample_mosaic_halves_resolution_and_scales() -> None:
    values = np.arange(48, dtype=np.float32).reshape(6, 8)
    seed = RadarMosaic(
        values=values,
        timestamp=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        proj_def=_SEED.proj_def,
        x_scale=500.0, y_scale=500.0,
        ul_lon=_SEED.ul_lon, ul_lat=_SEED.ul_lat,
        ur_lon=_SEED.ur_lon, ur_lat=_SEED.ur_lat,
        ll_lon=_SEED.ll_lon, ll_lat=_SEED.ll_lat,
        lr_lon=_SEED.lr_lon, lr_lat=_SEED.lr_lat,
    )
    out = downsample_mosaic(seed, factor=2)

    assert out.values.shape == (3, 4)
    assert out.x_scale == 1000.0
    assert out.y_scale == 1000.0
    # Spatial extent (corner lon/lats) is unchanged — same coverage, lower res.
    assert out.ul_lon == seed.ul_lon
    assert out.lr_lat == seed.lr_lat
    # Each output cell = mean of its 2x2 source block.
    np.testing.assert_allclose(out.values[0, 0], values[:2, :2].mean(), rtol=1e-5)
    np.testing.assert_allclose(out.values[2, 3], values[4:6, 6:8].mean(), rtol=1e-5)


def test_downsample_mosaic_is_nan_aware() -> None:
    values = np.ones((4, 4), dtype=np.float32)
    values[0, 0] = np.nan  # one NaN in the top-left 2x2 block
    values[2, 2] = values[2, 3] = values[3, 2] = values[3, 3] = np.nan  # all-NaN block
    seed = RadarMosaic(
        values=values, timestamp=_SEED.timestamp,
        proj_def=_SEED.proj_def, x_scale=500.0, y_scale=500.0,
        ul_lon=_SEED.ul_lon, ul_lat=_SEED.ul_lat,
        ur_lon=_SEED.ur_lon, ur_lat=_SEED.ur_lat,
        ll_lon=_SEED.ll_lon, ll_lat=_SEED.ll_lat,
        lr_lon=_SEED.lr_lon, lr_lat=_SEED.lr_lat,
    )
    out = downsample_mosaic(seed, factor=2)

    # Block with one NaN: mean of remaining 3 finite cells (all 1.0) = 1.0.
    assert out.values[0, 0] == 1.0
    # Block with 4 NaNs: result is NaN.
    assert np.isnan(out.values[1, 1])


def test_downsample_mosaic_factor_1_returns_input(tmp_path: Path) -> None:
    out = downsample_mosaic(_SEED, factor=1)
    assert out is _SEED
