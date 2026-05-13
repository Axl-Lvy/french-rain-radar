"""Tests for the manifest reader / writer / validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from radar.manifest import empty_manifest, read_manifest, validate_manifest, write_manifest


def test_example_manifest_is_valid(example_manifest_path: Path) -> None:
    manifest = json.loads(example_manifest_path.read_text())
    validate_manifest(manifest)


def test_empty_manifest_is_valid() -> None:
    m = empty_manifest(
        bbox={"latMin": 43.6, "latMax": 44.2, "lonMin": 4.6, "lonMax": 5.6},
        tile_size={"width": 512, "height": 384},
        color_scale="rainviewer-original",
    )
    validate_manifest(m)


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    m = empty_manifest(
        bbox={"latMin": 43.6, "latMax": 44.2, "lonMin": 4.6, "lonMax": 5.6},
        tile_size={"width": 512, "height": 384},
        color_scale="rainviewer-original",
    )
    write_manifest(target, m)
    again = read_manifest(target)
    assert again["bbox"]["latMin"] == 43.6


def test_validation_rejects_bad_version() -> None:
    m = empty_manifest(
        bbox={"latMin": 43.6, "latMax": 44.2, "lonMin": 4.6, "lonMax": 5.6},
        tile_size={"width": 512, "height": 384},
        color_scale="rainviewer-original",
    )
    m["manifestVersion"] = 999
    with pytest.raises(ValidationError):
        validate_manifest(m)
