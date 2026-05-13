"""Optical-flow nowcasting via pysteps.

Takes the latest N observed radar frames, extrapolates them ``lead_time_min``
minutes ahead, and yields the predicted fields.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import numpy as np
import structlog

log = structlog.get_logger(__name__)


def extrapolate(
    frames: list[np.ndarray],
    *,
    base_time: datetime,
    step_min: int = 5,
    lead_time_min: int = 60,
) -> Iterator[tuple[datetime, np.ndarray]]:
    """Yield ``(valid_time, frame)`` pairs from now to base_time + lead_time_min.

    Args:
        frames: list of consecutive radar mm/h fields, oldest first, same shape.
        base_time: observation time of the most recent frame.
        step_min: cadence of the source frames (5 min for the French mosaic).
        lead_time_min: how far ahead to extrapolate.

    Returns:
        Iterator of (valid_time, mm/h_array). Values past lead_time_min
        progressively lose skill; clients should distinguish nowcast from
        forecast in the UI.
    """
    from pysteps import motion, nowcasts

    if len(frames) < 2:
        raise ValueError("pysteps needs at least 2 frames for motion estimation")

    stack = np.stack(frames)
    oflow_method = motion.get_method("LK")
    velocity = oflow_method(stack)

    n_steps = lead_time_min // step_min
    extrapolator = nowcasts.get_method("extrapolation")
    predicted = extrapolator(stack[-1], velocity, n_steps)

    for i, field in enumerate(predicted, start=1):
        yield base_time + timedelta(minutes=i * step_min), field
