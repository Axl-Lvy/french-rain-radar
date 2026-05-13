"""Tests for the `radar nowcast` CLI command.

These tests monkeypatch ``radar.nowcast.extrapolate`` so they do not require
the optional ``nowcast`` extra (pysteps) to be installed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from radar.cli import app
from radar.radar_hdf5 import RadarMosaic, write_mosaic

runner = CliRunner()

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


def _ts_url(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _seed_radar_files(tile_dir: Path, n: int) -> list[datetime]:
    radar = tile_dir / "sources" / "radar"
    radar.mkdir(parents=True)
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    timestamps: list[datetime] = []
    for i in range(n):
        ts = base + timedelta(minutes=5 * i)
        values = np.full((6, 8), float(i + 1) * 0.5, dtype=np.float32)
        write_mosaic(radar / f"{_ts_url(ts)}.h5", values, seed=_SEED, timestamp=ts)
        timestamps.append(ts)
    return timestamps


@pytest.fixture
def tile_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RADAR_TILE_DIR", str(tmp_path))
    # Settings requires non-empty Météo-France tokens for the ingest commands
    # but the nowcast command never instantiates the client; still, providing
    # placeholders keeps Settings happy if the validation widens later.
    monkeypatch.setenv("METEOFRANCE_TOKEN_AROME", "test")
    monkeypatch.setenv("METEOFRANCE_TOKEN_RADAR", "test")
    return tmp_path


def test_skips_when_no_radar_sources(tile_dir: Path) -> None:
    result = runner.invoke(app, ["nowcast"])
    assert result.exit_code == 0, result.output
    assert not (tile_dir / "sources" / "nowcast").exists()
    assert not (tile_dir / "manifest.json").exists()


def test_skips_when_only_one_radar_frame(tile_dir: Path) -> None:
    _seed_radar_files(tile_dir, n=1)
    result = runner.invoke(app, ["nowcast"])
    assert result.exit_code == 0, result.output
    assert not (tile_dir / "sources" / "nowcast").exists()


def test_skips_when_pysteps_missing(
    tile_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_radar_files(tile_dir, n=4)

    def _missing(*args: object, **kwargs: object) -> Iterator[tuple[datetime, np.ndarray]]:
        raise ModuleNotFoundError("No module named 'pysteps'")

    monkeypatch.setattr("radar.nowcast.extrapolate", _missing)

    result = runner.invoke(app, ["nowcast"])
    assert result.exit_code == 0, result.output
    assert not (tile_dir / "sources" / "nowcast").exists()


def test_happy_path_writes_12_frames_and_replaces_cache(
    tile_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    radar_times = _seed_radar_files(tile_dir, n=4)
    base_time = radar_times[-1]

    stale_cache = tile_dir / "cache" / "nowcast" / "stale" / "5" / "16" / "12.png"
    stale_cache.parent.mkdir(parents=True)
    stale_cache.write_bytes(b"old")
    stale_source = tile_dir / "sources" / "nowcast" / "stale.h5"
    stale_source.parent.mkdir(parents=True, exist_ok=True)
    stale_source.write_bytes(b"old")

    captured: dict[str, object] = {}

    def _fake_extrapolate(
        frames: list[np.ndarray],
        *,
        base_time: datetime,
        step_min: int = 5,
        lead_time_min: int = 60,
    ) -> Iterator[tuple[datetime, np.ndarray]]:
        captured["n_frames"] = len(frames)
        captured["base_time"] = base_time
        n_steps = lead_time_min // step_min
        for i in range(1, n_steps + 1):
            yield base_time + timedelta(minutes=step_min * i), np.full(
                frames[-1].shape, 0.3, dtype=np.float32
            )

    monkeypatch.setattr("radar.nowcast.extrapolate", _fake_extrapolate)

    result = runner.invoke(app, ["nowcast"])
    assert result.exit_code == 0, result.output

    assert captured["n_frames"] == 4
    assert captured["base_time"] == base_time

    sources = sorted((tile_dir / "sources" / "nowcast").glob("*.h5"))
    assert len(sources) == 12
    assert not stale_source.exists()
    assert not stale_cache.exists()

    manifest = json.loads((tile_dir / "manifest.json").read_text())
    nowcast_layer = manifest["layers"]["nowcast"]
    assert nowcast_layer["tileUrlTemplate"] == "nowcast/{timestamp}/{z}/{x}/{y}.png"
    assert len(nowcast_layer["frames"]) == 12

    first_predicted = base_time + timedelta(minutes=5)
    last_predicted = base_time + timedelta(minutes=60)
    assert (
        nowcast_layer["frames"][0]["timestamp"]
        == first_predicted.isoformat().replace("+00:00", "Z")
    )
    assert (
        nowcast_layer["frames"][-1]["timestamp"]
        == last_predicted.isoformat().replace("+00:00", "Z")
    )


def test_uses_only_last_history_frames(
    tile_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If 10 radar files exist, only the last 4 are passed to extrapolate."""
    _seed_radar_files(tile_dir, n=10)

    captured: dict[str, object] = {}

    def _fake_extrapolate(
        frames: list[np.ndarray],
        *,
        base_time: datetime,
        step_min: int = 5,
        lead_time_min: int = 60,
    ) -> Iterator[tuple[datetime, np.ndarray]]:
        captured["n_frames"] = len(frames)
        # Distinguish from the older frames by their constant value.
        captured["last_value"] = float(frames[-1][0, 0])
        yield base_time + timedelta(minutes=5), np.zeros(frames[-1].shape, dtype=np.float32)

    monkeypatch.setattr("radar.nowcast.extrapolate", _fake_extrapolate)

    result = runner.invoke(app, ["nowcast"])
    assert result.exit_code == 0, result.output
    assert captured["n_frames"] == 4
    # The newest seed value is i=9 -> (9+1)*0.5 = 5.0.
    assert captured["last_value"] == pytest.approx(5.0, abs=0.01)
