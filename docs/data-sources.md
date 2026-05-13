# Data sources

Both APIs are free under [Licence Ouverte / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/) via <https://portail-api.meteofrance.fr/>. One API key per subscription, passed in the `apikey` request header (keys are JWTs, ~1.6 KB each).

The pipeline composes three layers from these:

- **radar** — observed precipitation, refreshed every 5 min
- **nowcast** — local pysteps extrapolation of the radar history, 0–60 min
- **forecast** — AROME-PI NWP, 0–6 h horizon, hourly runs

## API 1 — AROME-PI (forecast layer)

Portal page: <https://portail-api.meteofrance.fr/web/en/api/PaquetAROME>

| Property | Value |
|---|---|
| Base URL | `https://public-api.meteofrance.fr/public/aromepi/1.0/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS` |
| Protocol | WCS 2.0.1 |
| Auth | `apikey: <jwt>` header |
| Rate limit | 100 req/min |
| Coverage of interest | `TOTAL_WATER_PRECIPITATION__GROUND_OR_WATER_SURFACE___<RUN>_PT15M` |
| `<RUN>` format | `YYYY-MM-DDTHH.MM.SSZ` (e.g. `2026-05-13T20.00.00Z`) |
| Run cadence | hourly |
| Time axis | 24 steps in seconds offsets: 900, 1800, 2700, …, 21600 (+15 min through +6 h, in 15-min steps) |
| Spatial CRS | EPSG:4326 (regular lat/lon, 0.01° ≈ 1.1 km) |
| Spatial extent | lon −12 to +16, lat 37.5 to 55.4 (Western Europe) |
| GRIB short-name | `tirf` ("Time integral of rain flux") |
| Unit | `kg m⁻²` = mm of water over the 15-min accumulation window. Multiply by 4 for mm/h. |
| Native format | `application/wmo-grib` (also offers `image/tiff`) |

### Endpoints

```
GET /GetCapabilities?service=WCS&version=2.0.1&language=eng
GET /DescribeCoverage?service=WCS&version=2.0.1&coverageid=<COVERAGE_ID>
GET /GetCoverage?service=WCS&version=2.0.1
                 &coverageid=<COVERAGE_ID>
                 &format=application%2Fwmo-grib
                 &subset=long(<lon_min>,<lon_max>)
                 &subset=lat(<lat_min>,<lat_max>)
                 &subset=time(<seconds_offset>)
```

### Quirks

- **Time subset must slice, not trim**: `time(900,900)` is rejected with `InvalidSubsetting`. Use the single-value form: `time(900)`.
- **`format` must be URL-encoded**: `application%2Fwmo-grib`.
- GetCapabilities is ~36 K lines — parse with `xml.etree.ElementTree.iterparse`, don't hold it all in memory.

## API 2 — Radar data (radar layer)

Portal page: <https://portail-api.meteofrance.fr/web/en/api/DonneesPubliquesRadar>

| Property | Value |
|---|---|
| Base URL | `https://public-api.meteofrance.fr/public/DPRadar/v1` |
| Protocol | Bespoke REST (HATEOAS-style; not WCS) |
| Auth | `apikey: <jwt>` header |
| Rate limit | 850 req / 5 min |
| Zone | `METROPOLE` |
| Observation | `LAME_D_EAU` (5-min precipitation accumulation) |
| Frame cadence | every 5 min |
| Available `maille` | `500` (HDF5, ODIM_H5/V2.3) or `1000` (gzipped BUFR) |
| **We use `maille=500`** | ~2 MB per frame, ODIM_H5 trivially parses with h5py |
| Native projection | Polar Stereographic, `+proj=stere +lat_0=90 +lon_0=0 +lat_ts=45 +ellps=WGS84 +x_0=619652.07 +y_0=5262818.34 +datum=WGS84` |
| Grid | 3472 × 3472 cells at 500 m spacing |
| Coverage | Western Europe: UL 53.67/-9.97, UR 52.55/17.56, LL 38.14/-6.72, LR 37.46/11.98 |

### Endpoints

```
GET /mosaiques
GET /mosaiques/METROPOLE
GET /mosaiques/METROPOLE/observations
GET /mosaiques/METROPOLE/observations/LAME_D_EAU        # ← cheap, returns validity_time
GET /mosaiques/METROPOLE/observations/LAME_D_EAU/produit?maille=500
```

The fourth call returns a small JSON descriptor whose `links[<latest>].validity_time` is the timestamp of the freshest frame available. Use it for the dedup check before pulling the heavy `produit`.

### HDF5 structure

```
/                             attrs: Conventions=ODIM_H5/V2_3
/where                        attrs: projdef, UL/UR/LL/LR_lat+lon, xsize, ysize, xscale, yscale
/dataset1/what                attrs: startdate, starttime, enddate, endtime  (= 5-min window)
/dataset1/data1/data          shape=(3472, 3472), dtype=uint16
/dataset1/data1/what          attrs: gain=0.01, offset=0.0, nodata=65535, undetect=65534, quantity=ACRR
```

Conversion: `mm = raw * gain + offset`, with `raw ∈ {nodata, undetect}` → NaN. `mm/h = mm × 12`.

## Citation

The Licence Ouverte requires crediting Météo-France visibly. The client UI surfaces "Source: Météo-France" on the map view; the manifest carries an `attribution` field for future flexibility.
