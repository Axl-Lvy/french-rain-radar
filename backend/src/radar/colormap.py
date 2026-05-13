"""Rainfall-rate (mm/h) → RGBA colour ramp.

The default ramp loosely mirrors RainViewer's "Original" palette:
transparent for no rain, light blue → blue → green → yellow → orange → red → magenta
for increasing intensities.

If you change the ramp, also change the ``color_scale`` identifier in the
manifest so clients can render a matching legend.
"""

from __future__ import annotations

import numpy as np

# (mm/h threshold, R, G, B, A)
RAINVIEWER_ORIGINAL: list[tuple[float, int, int, int, int]] = [
    (0.0,    0,   0,   0,   0),
    (0.1,  150, 220, 240, 180),
    (0.5,   80, 160, 230, 200),
    (1.0,   40, 110, 220, 220),
    (2.0,   60, 200,  80, 230),
    (5.0,  250, 230,  60, 240),
    (10.0, 250, 150,  40, 245),
    (20.0, 230,  60,  40, 250),
    (50.0, 180,  20, 140, 255),
]


def colorize(values: np.ndarray, *, scale: str = "rainviewer-original") -> np.ndarray:
    """Map an HxW array of mm/h values to an HxWx4 RGBA uint8 array.

    NaNs become fully transparent. Values are linearly interpolated between
    the breakpoints of the chosen ramp.
    """
    if scale != "rainviewer-original":
        raise ValueError(f"unknown color scale: {scale}")
    ramp = RAINVIEWER_ORIGINAL
    breakpoints = np.array([bp[0] for bp in ramp])
    colors = np.array([bp[1:] for bp in ramp], dtype=np.float32)

    h, w = values.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    mask = ~np.isnan(values)
    if not mask.any():
        return out

    v = np.clip(values[mask], breakpoints[0], breakpoints[-1])
    idx = np.searchsorted(breakpoints, v, side="right") - 1
    idx = np.clip(idx, 0, len(breakpoints) - 2)
    lo = breakpoints[idx]
    hi = breakpoints[idx + 1]
    t = ((v - lo) / np.maximum(hi - lo, 1e-9))[:, None]
    rgba = colors[idx] + t * (colors[idx + 1] - colors[idx])
    out[mask] = np.clip(rgba, 0, 255).astype(np.uint8)
    return out
