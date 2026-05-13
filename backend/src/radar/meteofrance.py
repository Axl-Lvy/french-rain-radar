"""Météo-France open-data API client.

Fetches GRIB2 files for two products:

- PRECIP-FRANCE: 1-km radar mosaic, 5-min cadence (observed precipitation).
- AROME-NWC: 1.3-km numerical forecast, hourly runs, 0-6 h horizon.

Authentication uses the API token issued by https://portail-api.meteofrance.fr/.
Set ``METEOFRANCE_TOKEN`` in the environment.

NOTE: this is a scaffold; endpoint paths must be validated against the current
Météo-France API docs at scaffold time.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)


class MeteoFranceClient:
    """Thin sync client over the Météo-France open-data API.

    Two subscriptions are needed:
    - **AROME-PI** for 0-6 h forecast (WCS endpoint family)
    - **Radar data** for the observed mosaic

    Each subscription has its own apikey, passed via the ``apikey`` request
    header. If one portal Application is subscribed to both APIs the same
    key works for both, but the client keeps them separate so per-API
    revocation stays possible.
    """

    BASE_URL = "https://public-api.meteofrance.fr"

    def __init__(self, *, arome_token: str, radar_token: str, timeout: float = 30.0) -> None:
        self._arome_token = arome_token
        self._radar_token = radar_token
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout, headers={"Accept": "application/octet-stream"})

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MeteoFranceClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ radar

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_latest_radar(self, *, dest: Path) -> datetime:
        """Download the latest radar mosaic GRIB2 to ``dest``.

        Uses the ``radar_token`` apikey. Returns the observation timestamp
        parsed from the response or filename.
        """
        raise NotImplementedError("TODO: implement against the Radar data WCS GetCoverage endpoint")

    # ------------------------------------------------------------------ AROME-PI

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_latest_arome_pi(self, *, dest_dir: Path) -> list[Path]:
        """Download the latest AROME-PI run; returns the per-leadtime GRIB files.

        Uses the ``arome_token`` apikey. Endpoint:
        ``/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS/GetCoverage``.
        """
        raise NotImplementedError("TODO: implement against the AROME-PI WCS GetCoverage endpoint")
