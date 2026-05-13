"""Tests for the PNG renderer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from radar.colormap import colorize
from radar.render import write_png


def test_colorize_handles_nans() -> None:
    arr = np.array([[np.nan, 0.0, 1.0], [5.0, 10.0, 30.0]])
    rgba = colorize(arr)
    assert rgba.shape == (2, 3, 4)
    assert rgba[0, 0, 3] == 0  # NaN -> fully transparent


def test_write_png_atomic(tmp_path: Path) -> None:
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[..., 3] = 255
    out = tmp_path / "out.png"
    write_png(arr, out)
    assert out.exists()
    assert Image.open(out).size == (4, 4)


def test_write_png_rejects_wrong_shape(tmp_path: Path) -> None:
    arr = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        write_png(arr, tmp_path / "bad.png")
