"""Placeholder tests for the GRIB reader.

Real tests will exercise ``radar.grib.read_precip`` against a fixture
GRIB2 file in ``tests/fixtures/sample.grib2``. Add the fixture once the
Météo-France endpoint has been wired up.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs a sample GRIB2 fixture; see backend/tests/fixtures/README.md")
def test_read_precip_sample() -> None:
    pass
