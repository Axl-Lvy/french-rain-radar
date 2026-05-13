"""Tests for the ODIM_H5 reader/writer pair."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from radar.radar_hdf5 import RadarMosaic, read_mosaic, write_mosaic

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
