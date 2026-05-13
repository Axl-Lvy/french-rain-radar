"""Optical-flow nowcasting via pysteps.

Two methods are supported:

* ``"extrapolation"`` — Lucas-Kanade motion + plain semi-Lagrangian
  advection. Cheap, deterministic, but assumes precip is purely transported
  (no growth/decay).
* ``"sprog"`` — Lucas-Kanade motion + S-PROG (deterministic cascade with
  AR(2) per scale, mean probability matching). Models growth/decay so the
  30-60 min horizon retains more skill, at the cost of an FFT-based
  cascade decomposition per timestep.

Both return ``(valid_time, mm/h_array)`` pairs from now to lead_time_min.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Literal

import numpy as np
import structlog

log = structlog.get_logger(__name__)

NowcastMethod = Literal["extrapolation", "sprog"]


def extrapolate(
    frames: list[np.ndarray],
    *,
    base_time: datetime,
    step_min: int = 5,
    lead_time_min: int = 60,
    method: NowcastMethod = "extrapolation",
) -> Iterator[tuple[datetime, np.ndarray]]:
    """Yield ``(valid_time, frame)`` pairs from now to base_time + lead_time_min.

    Args:
        frames: list of consecutive radar mm/h fields, oldest first, same shape.
        base_time: observation time of the most recent frame.
        step_min: cadence of the source frames (5 min for the French mosaic).
        lead_time_min: how far ahead to extrapolate.
        method: ``"extrapolation"`` (LK + semi-Lagrangian advection) or
            ``"sprog"`` (LK + AR(2) cascade with mean probability matching).

    Returns:
        Iterator of (valid_time, mm/h_array). Values past lead_time_min
        progressively lose skill; clients should distinguish nowcast from
        forecast in the UI.
    """
    from pysteps import motion, nowcasts

    if len(frames) < 2:
        raise ValueError("pysteps needs at least 2 frames for motion estimation")

    stack = np.stack(frames).astype(np.float32)
    # pysteps LK can't read NaN; the radar mosaic encodes nodata/undetect as NaN.
    # Zero-fill before motion estimation; out-of-domain pixels in the extrapolated
    # output stay NaN.
    stack_filled = np.where(np.isnan(stack), np.float32(0.0), stack)
    oflow_method = motion.get_method("LK")
    velocity = oflow_method(stack_filled)

    n_steps = lead_time_min // step_min

    if method == "extrapolation":
        extrapolator = nowcasts.get_method("extrapolation")
        predicted = extrapolator(stack_filled[-1], velocity, n_steps)
    elif method == "sprog":
        predicted = _sprog_forecast(stack_filled, velocity, n_steps)
    else:
        raise ValueError(f"unknown nowcast method: {method!r}")

    for i, field in enumerate(predicted, start=1):
        yield base_time + timedelta(minutes=i * step_min), field


def _sprog_forecast(
    stack: np.ndarray,
    velocity: np.ndarray,
    n_steps: int,
) -> np.ndarray:
    """Run pysteps S-PROG on a stack of mm/h frames.

    S-PROG operates in dBR space (log-rainrate) where the precipitation field
    is closer to Gaussian and the AR(2) noise model is well-posed. We
    forward-transform here and inverse-transform the output back to mm/h so
    callers stay in physical units end-to-end.
    """
    from pysteps import nowcasts
    from pysteps.utils import transformation

    # 0.1 mm/h is the conventional precip threshold in mm/h; in dB that's
    # -10 (10*log10(0.1)). Anything below counts as "dry" both in the AR(2)
    # noise model and in the final probability matching.
    precip_thr_mmh = 0.1
    precip_thr_db = 10.0 * np.log10(precip_thr_mmh)

    stack_db, _ = transformation.dB_transform(
        stack, threshold=precip_thr_mmh, zerovalue=-15.0
    )

    # S-PROG requires exactly ar_order + 1 = 3 frames; pass the most recent three.
    forecast_method = nowcasts.get_method("sprog")
    predicted_db = forecast_method(
        stack_db[-3:],
        velocity,
        n_steps,
        n_cascade_levels=6,
        precip_thr=precip_thr_db,
        ar_order=2,
        probmatching_method="mean",
    )

    predicted, _ = transformation.dB_transform(
        predicted_db, threshold=precip_thr_db, inverse=True
    )
    return predicted
