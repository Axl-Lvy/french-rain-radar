"""Tests for the dedup helper."""

from __future__ import annotations

from datetime import UTC, datetime

from radar.manifest import empty_manifest, most_recent_timestamp

_BBOX = {"latMin": 41.3, "latMax": 51.5, "lonMin": -5.5, "lonMax": 10.0}


def _make_manifest(radar_timestamps: list[str]) -> dict:
    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    m["layers"]["radar"] = {
        "tileUrlTemplate": "radar/{timestamp}/{z}/{x}/{y}.png",
        "minZoom": 5,
        "maxZoom": 10,
        "frames": [{"timestamp": ts} for ts in radar_timestamps],
    }
    return m


def test_most_recent_timestamp_empty_layer_returns_none() -> None:
    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    assert most_recent_timestamp(m, "radar") is None


def test_most_recent_timestamp_picks_max() -> None:
    m = _make_manifest([
        "2026-05-13T14:15:00Z",
        "2026-05-13T14:25:00Z",
        "2026-05-13T14:20:00Z",
    ])
    assert most_recent_timestamp(m, "radar") == datetime(2026, 5, 13, 14, 25, tzinfo=UTC)


def test_most_recent_timestamp_missing_layer_returns_none() -> None:
    m = _make_manifest([])
    m["layers"].pop("forecast", None)
    assert most_recent_timestamp(m, "forecast") is None
