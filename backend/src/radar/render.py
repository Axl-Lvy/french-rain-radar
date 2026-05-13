"""PNG rendering — numpy → file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def write_png(rgba: np.ndarray, dest: Path) -> None:
    """Write an RGBA uint8 array to ``dest`` atomically.

    ``dest`` is replaced atomically so clients never observe a half-written file.
    """
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected HxWx4 uint8 array")

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=dest.name + ".", suffix=".tmp", dir=str(dest.parent))
    os.close(fd)
    tmp = Path(tmp_str)
    try:
        Image.fromarray(rgba, mode="RGBA").save(tmp, format="PNG", optimize=False)
        os.replace(tmp, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
