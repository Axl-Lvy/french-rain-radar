"""Tests for the tile-server HTTP surface (FastAPI handlers)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from radar.tile_server import app

client = TestClient(app)


def test_tile_out_of_range_rejected() -> None:
    """A tile coordinate outside [0, 2**z) must 404 before any rendering work.

    At z=2 the grid is 4x4, so x=4 and y=4 are both invalid. The guard runs
    before the source-file lookup, so the response is a deterministic 404
    regardless of whether sources exist on disk.
    """
    r = client.get("/radar/2026-05-13T20-45-00Z/2/4/0.png")
    assert r.status_code == 404
    assert r.json()["detail"] == "tile out of range"

    r = client.get("/radar/2026-05-13T20-45-00Z/2/0/4.png")
    assert r.status_code == 404


def test_tile_in_range_passes_guard() -> None:
    """A legitimate (z, x, y) passes the range guard; the request only fails
    later because there is no source file in the test environment."""
    r = client.get("/radar/2026-05-13T20-45-00Z/2/3/3.png")
    assert r.status_code == 404
    assert "tile out of range" not in r.text


def test_tile_z0_only_accepts_0_0() -> None:
    """Zoom 0 has a single tile at (0, 0)."""
    r = client.get("/radar/2026-05-13T20-45-00Z/0/1/0.png")
    assert r.status_code == 404
    assert r.json()["detail"] == "tile out of range"
