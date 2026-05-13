"""Tests for the manifest reader / writer / validator (v2 schema)."""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

import pytest
from jsonschema import ValidationError

from radar.manifest import (
    empty_manifest,
    read_manifest,
    upsert_layer_frame,
    validate_manifest,
    write_manifest,
)

_BBOX = {"latMin": 41.3, "latMax": 51.5, "lonMin": -5.5, "lonMax": 10.0}


def test_example_manifest_is_valid(example_manifest_path: Path) -> None:
    manifest = json.loads(example_manifest_path.read_text())
    validate_manifest(manifest)


def test_empty_manifest_is_valid() -> None:
    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    assert m["manifestVersion"] == 2
    validate_manifest(m)


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    write_manifest(target, m)
    again = read_manifest(target)
    assert again["bbox"]["latMin"] == _BBOX["latMin"]


def test_validation_rejects_bad_version() -> None:
    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    m["manifestVersion"] = 999
    with pytest.raises(ValidationError):
        validate_manifest(m)


def test_upsert_creates_layer_then_dedupes() -> None:
    from datetime import datetime

    m = empty_manifest(bbox=_BBOX, color_scale="rainviewer-original")
    ts = datetime(2026, 5, 13, 20, 50, tzinfo=UTC)
    upsert_layer_frame(
        m, "radar",
        timestamp=ts,
        tile_url_template="radar/{timestamp}/{z}/{x}/{y}.png",
        min_zoom=5, max_zoom=10,
    )
    upsert_layer_frame(  # same ts -> no-op
        m, "radar",
        timestamp=ts,
        tile_url_template="radar/{timestamp}/{z}/{x}/{y}.png",
        min_zoom=5, max_zoom=10,
    )
    assert len(m["layers"]["radar"]["frames"]) == 1
    validate_manifest(m)
