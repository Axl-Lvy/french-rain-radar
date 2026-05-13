"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_path(repo_root: Path) -> Path:
    return repo_root / "schema" / "manifest.schema.json"


@pytest.fixture
def example_manifest_path(repo_root: Path) -> Path:
    return repo_root / "schema" / "examples" / "manifest.example.json"
