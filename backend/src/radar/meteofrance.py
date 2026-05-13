"""Météo-France open-data API client.

Two APIs from <https://portail-api.meteofrance.fr/>, each with its own apikey:

- **AROME-PI** (`aromepi/1.0/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS`) —
  numerical forecast, hourly runs, 0-6 h horizon at 15-min steps, 0.01° (~1.1 km)
  regular lat/lon grid, GRIB2 output.
- **DPRadar** (`DPRadar/v1`) — observed radar mosaic, 5-min cadence,
  ODIM_H5 / Polar Stereographic at 500 m, served as HDF5.

Both expect the apikey in an ``apikey: <jwt>`` header. See
``docs/data-sources.md`` for the full shape.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import structlog
from defusedxml.ElementTree import iterparse as _safe_iterparse
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)

# ----------------------------------------------------------------------- URLs

AROME_BASE = (
    "https://public-api.meteofrance.fr/public/aromepi/1.0/wcs/"
    "MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS"
)
RADAR_BASE = "https://public-api.meteofrance.fr/public/DPRadar/v1"

# AROME-PI: time axis of the PT15M coverage in seconds offsets from run time.
AROME_LEAD_TIMES_S: tuple[int, ...] = tuple(range(900, 21600 + 1, 900))  # 24 values: 15min..360min

# Regex pulling the run reference time out of an AROME-PI coverage ID.
_AROME_COVERAGE_RE = re.compile(
    r"TOTAL_WATER_PRECIPITATION__GROUND_OR_WATER_SURFACE___"
    r"(?P<run>\d{4}-\d{2}-\d{2}T\d{2}\.\d{2}\.\d{2}Z)_PT15M"
)


# --------------------------------------------------------------------- models


@dataclass(frozen=True)
class RadarFrame:
    """A single radar mosaic frame fetched from DPRadar."""

    validity_time: datetime  # UTC
    path: Path               # on-disk HDF5 file


@dataclass(frozen=True)
class AromeForecastFrame:
    """A single AROME-PI lead-time fetched as GRIB2."""

    run_time: datetime       # UTC reference time of the run
    valid_time: datetime     # UTC = run_time + lead_seconds
    lead_seconds: int
    path: Path               # on-disk GRIB2 file


# -------------------------------------------------------------------- client


class MeteoFranceClient:
    """Sync client over the two Météo-France APIs we use."""

    def __init__(
        self,
        *,
        arome_token: str,
        radar_token: str,
        timeout: float = 60.0,
    ) -> None:
        if not arome_token or not radar_token:
            raise ValueError("both arome_token and radar_token must be non-empty")
        self._arome_token = arome_token
        self._radar_token = radar_token
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MeteoFranceClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # =================================================================== AROME

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def get_arome_capabilities(self) -> bytes:
        """Fetch the raw GetCapabilities XML. ~2 MB; cache at the caller if needed."""
        r = self._client.get(
            f"{AROME_BASE}/GetCapabilities",
            params={"service": "WCS", "version": "2.0.1", "language": "eng"},
            headers={"apikey": self._arome_token},
        )
        r.raise_for_status()
        return r.content

    def latest_arome_run(self, *, capabilities: bytes | None = None) -> datetime | None:
        """Parse GetCapabilities to find the most recent AROME-PI run time."""
        xml = capabilities or self.get_arome_capabilities()
        latest: datetime | None = None
        for _, elem in _safe_iterparse(_BytesReader(xml), events=("end",)):
            if elem.tag.endswith("}CoverageId"):
                m = _AROME_COVERAGE_RE.match(elem.text or "")
                if m:
                    run = datetime.strptime(m.group("run"), "%Y-%m-%dT%H.%M.%SZ").replace(
                        tzinfo=UTC
                    )
                    if latest is None or run > latest:
                        latest = run
                elem.clear()
        return latest

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_arome_leadtime(
        self,
        run_time: datetime,
        lead_seconds: int,
        *,
        bbox: tuple[float, float, float, float],
        dest_dir: Path,
    ) -> AromeForecastFrame | None:
        """Download one AROME-PI lead-time GRIB2 to ``dest_dir``.

        Returns ``None`` if the leadtime is not yet published (HTTP 404). The
        model trickles out leadtimes incrementally during the hour following
        the run reference time, so a 404 here is normal early in the run and
        is **not** retried; transient errors (5xx, network) still retry.
        """
        run_label = run_time.astimezone(UTC).strftime("%Y-%m-%dT%H.%M.%SZ")
        coverage_id = (
            f"TOTAL_WATER_PRECIPITATION__GROUND_OR_WATER_SURFACE___{run_label}_PT15M"
        )
        lon_min, lat_min, lon_max, lat_max = bbox
        params = [
            ("service", "WCS"),
            ("version", "2.0.1"),
            ("coverageid", coverage_id),
            ("format", "application/wmo-grib"),
            ("subset", f"long({lon_min},{lon_max})"),
            ("subset", f"lat({lat_min},{lat_max})"),
            ("subset", f"time({lead_seconds})"),
        ]
        r = self._client.get(
            f"{AROME_BASE}/GetCoverage",
            params=params,
            headers={"apikey": self._arome_token},
        )
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            log.debug("arome.getcoverage.error.body", body=r.text[:500])
            raise RuntimeError(
                f"AROME-PI GetCoverage failed: HTTP {r.status_code} "
                f"content-type={r.headers.get('content-type', 'unknown')}"
            )
        if not r.content.startswith(b"GRIB"):
            raise RuntimeError(f"AROME-PI response is not a GRIB: {r.content[:200]!r}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        valid_time = run_time + timedelta(seconds=lead_seconds)
        dest = dest_dir / f"arome_{valid_time.strftime('%Y%m%dT%H%M%SZ')}.grib2"
        dest.write_bytes(r.content)
        return AromeForecastFrame(
            run_time=run_time,
            valid_time=valid_time,
            lead_seconds=lead_seconds,
            path=dest,
        )

    def fetch_arome_run(
        self,
        run_time: datetime,
        *,
        bbox: tuple[float, float, float, float],
        dest_dir: Path,
        lead_times_s: tuple[int, ...] = AROME_LEAD_TIMES_S,
    ) -> Iterator[AromeForecastFrame]:
        """Yield available lead-time frames for a run, skipping any 404 (pending) ones."""
        for lead in lead_times_s:
            frame = self.fetch_arome_leadtime(
                run_time, lead, bbox=bbox, dest_dir=dest_dir
            )
            if frame is None:
                log.info("arome.leadtime.pending", run=run_time.isoformat(), lead_s=lead)
                continue
            yield frame

    # =================================================================== RADAR

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def latest_radar_validity(
        self,
        zone: str = "METROPOLE",
        observation: str = "LAME_D_EAU",
        *,
        maille: int = 500,
    ) -> datetime | None:
        """Cheap dedup probe: the observation descriptor lists the latest frame's validity_time."""
        r = self._client.get(
            f"{RADAR_BASE}/mosaiques/{zone}/observations/{observation}",
            headers={"apikey": self._radar_token},
        )
        r.raise_for_status()
        body = r.json()
        for link in body.get("links", []):
            href = link.get("href", "")
            if f"maille={maille}" in href and "validity_time" in link:
                return _parse_iso(link["validity_time"])
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def fetch_latest_radar(
        self,
        *,
        dest: Path,
        zone: str = "METROPOLE",
        observation: str = "LAME_D_EAU",
        maille: int = 500,
    ) -> RadarFrame:
        """Download the latest radar mosaic HDF5 to ``dest``."""
        validity = self.latest_radar_validity(zone, observation, maille=maille)
        if validity is None:
            raise RuntimeError(
                f"radar descriptor for {zone}/{observation}@{maille}m has no validity_time"
            )

        r = self._client.get(
            f"{RADAR_BASE}/mosaiques/{zone}/observations/{observation}/produit",
            params={"maille": maille},
            headers={"apikey": self._radar_token},
        )
        if r.status_code != 200:
            log.debug("radar.produit.error.body", body=r.text[:500])
            raise RuntimeError(
                f"radar produit failed: HTTP {r.status_code} "
                f"content-type={r.headers.get('content-type', 'unknown')}"
            )
        if not r.content.startswith(b"\x89HDF\r\n\x1a\n"):
            raise RuntimeError(f"radar response is not HDF5: magic={r.content[:8]!r}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return RadarFrame(validity_time=validity, path=dest)


# ----------------------------------------------------------------------- utils


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class _BytesReader:
    """Stream a bytes buffer to ElementTree.iterparse."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        if n < 0 or self._pos + n > len(self._data):
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk
