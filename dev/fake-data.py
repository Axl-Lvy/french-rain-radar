#!/usr/bin/env python
"""Generate synthetic radar / nowcast / forecast PNGs + a valid manifest.

Run via `make fake-data` or directly with `uv run python dev/fake-data.py`.

The output goes into `dev/data/tiles/` which is mounted into the dev Caddy
container by `dev/docker-compose.yml`. The synthetic "rain" drifts across the
bounding box so the animation in the client looks alive.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from radar.colormap import colorize  # noqa: E402
from radar.manifest import empty_manifest, write_manifest  # noqa: E402
from radar.render import write_png  # noqa: E402

OUT_DIR = REPO_ROOT / "dev" / "data" / "tiles"
WIDTH, HEIGHT = 512, 384
BBOX = {"latMin": 43.6, "latMax": 44.2, "lonMin": 4.6, "lonMax": 5.6}

# Frame plan
N_RADAR_FRAMES = 24       # 24 * 5 min = 2 h of past
N_NOWCAST_FRAMES = 12     # 12 * 5 min = 60 min ahead
N_FORECAST_FRAMES = 6     # 6 * 1 h = 6 h ahead
STEP_RADAR = timedelta(minutes=5)
STEP_FORECAST = timedelta(hours=1)


def synth_field(t_index: float, *, intensity: float) -> np.ndarray:
    """Generate a moving Gaussian blob of mm/h rain."""
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    cx = (WIDTH * 0.5) + math.cos(t_index * 0.4) * WIDTH * 0.3
    cy = (HEIGHT * 0.5) + math.sin(t_index * 0.4) * HEIGHT * 0.3
    sigma = WIDTH * 0.15
    blob = np.exp(-(((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * sigma ** 2)))
    return (blob * intensity).astype(np.float32)


def stamp(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H-%M-%S")


def write_layer(layer: str, frames: list[datetime], values_for: callable, manifest: dict) -> None:
    layer_dir = OUT_DIR / layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    for i, ts in enumerate(frames):
        rgba = colorize(values_for(i))
        rel = f"{layer}/{stamp(ts)}.png"
        write_png(rgba, OUT_DIR / rel)
        manifest["layers"][layer]["frames"].append({
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "url": rel,
        })


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0, second=0)
    now -= timedelta(minutes=now.minute % 5)

    manifest = empty_manifest(
        bbox=BBOX,
        tile_size={"width": WIDTH, "height": HEIGHT},
        color_scale="rainviewer-original",
    )

    radar_frames = [now - STEP_RADAR * (N_RADAR_FRAMES - 1 - i) for i in range(N_RADAR_FRAMES)]
    write_layer("radar", radar_frames,
                lambda i: synth_field(i, intensity=20.0), manifest)

    nowcast_frames = [now + STEP_RADAR * (i + 1) for i in range(N_NOWCAST_FRAMES)]
    write_layer("nowcast", nowcast_frames,
                lambda i: synth_field(N_RADAR_FRAMES + i, intensity=15.0), manifest)

    forecast_frames = [now + STEP_FORECAST * (i + 2) for i in range(N_FORECAST_FRAMES)]
    write_layer("forecast", forecast_frames,
                lambda i: synth_field(N_RADAR_FRAMES + N_NOWCAST_FRAMES + i * 4, intensity=10.0), manifest)

    write_manifest(OUT_DIR / "manifest.json", manifest)
    print(f"wrote {N_RADAR_FRAMES} radar + {N_NOWCAST_FRAMES} nowcast + {N_FORECAST_FRAMES} forecast frames")
    print(f"  -> {OUT_DIR}")


if __name__ == "__main__":
    main()
