# Architecture

## One-paragraph summary

A Python ingest pipeline runs on a Hetzner VPS, pulls radar + AROME-PI forecast data from Météo-France every 5 min / hour (systemd timers), and only **caches the raw source files** (HDF5 + GRIB2) under `sources/`. A FastAPI tile server (`radar-tileserver.service`, loopback `127.0.0.1:8765`) handles XYZ tile requests on cache-miss: load the cached source for the requested timestamp, reproject + colourise the 256×256 tile, write it to `cache/`, and return the bytes. **Caddy** fronts everything with HTTPS + HTTP basic auth + per-user rate limiting; its `file` matcher serves cache hits as pure static (~50 ms) and reverse-proxies misses to the tile server (~200 ms first time). The Kotlin Multiplatform client polls `manifest.json` for available frame timestamps and consumes them via MapLibre's `RasterSource` against each layer's `tileUrlTemplate`.

## Data flow

```
        ┌──────────────────────────────────────┐
        │  Météo-France open-data APIs          │
        │   - AROME-PI WCS                      │
        │   - DPRadar REST                      │
        └──────────────┬────────────────────────┘
                       │ HDF5 / GRIB2
                       ▼
   ┌────────────────────────────────────────────┐
   │  INGEST  (systemd timers, one-shot CLI)    │
   │                                            │
   │   radar ingest-radar  (every 5 min @ :30s) │
   │   radar ingest-arome  (hourly @ HH:10)     │
   │   radar nowcast       (every 5 min @ :02:30)│
   │   radar cleanup       (daily 03:30)        │
   │                                            │
   │  Only downloads sources; no rendering.     │
   └──────────────────────┬─────────────────────┘
                          │ writes
                          ▼
       /var/lib/radar/tiles/
         ├── manifest.json                # v2; lists timestamps
         ├── sources/
         │   ├── radar/<ts>.h5            # ODIM_H5, ~2 MB each
         │   ├── nowcast/<ts>.h5          # ODIM_H5 (extrapolated from radar)
         │   └── forecast/<ts>.grib2      # AROME-PI, ~3 MB each
         └── cache/
             ├── radar/<ts>/<z>/<x>/<y>.png
             ├── nowcast/<ts>/<z>/<x>/<y>.png
             └── forecast/<ts>/<z>/<x>/<y>.png

                          ▲                              ▲
                          │ writes (on miss)             │ reads (always)
   ┌──────────────────────────────────────┐  ┌──────────────────────────┐
   │  TILE SERVER (radar tile-server)     │  │  CADDY                   │
   │   FastAPI + uvicorn                  │  │  - HTTPS                 │
   │   127.0.0.1:8765                     │  │  - basic_auth            │
   │   On request:                        │  │  - rate_limit            │
   │     load source -> reproject ->      │◄─┤  - @tile path_regexp:    │
   │     colourise -> save PNG -> return  │  │      @cached file        │
   └──────────────────────────────────────┘  │      hit  -> file_server │
                                             │      miss -> reverse_proxy│
                                             └─────────────┬────────────┘
                                                           │ HTTPS
                                            ┌──────────────┼──────────────┐
                                            ▼              ▼              ▼
                                        Android          iOS            Wasm
                                          (Kotlin Multiplatform client)
```

## Why split into ingest + tile server?

Pre-rendering every tile of an XYZ pyramid covering all of France at z=5..9 would produce ~1400 tiles per frame × (12 radar/hour + 24 forecast/run) — most of them over ocean, fields, or zones nobody zooms into. The lazy split:

1. Renders only the tiles users actually request — drastically lower CPU + disk on the cheap VPS.
2. Caches each tile on first render, so the second request through the warm path is pure-static Caddy (sub-50 ms).
3. Supports arbitrary zoom (the server renders whatever `(z, x, y)` the client asks for), capped only by the source's intrinsic resolution.

ADR-0004 captures the trade-off; ADR-0002 is partially superseded.

## Sequence: one radar ingest cycle

1. `radar-ingest.timer` fires at `HH:MM:30` (every 5 min, 30 s after the minute so the latest MF frame is published).
2. `radar ingest-radar`:
   a. `MeteoFranceClient.latest_radar_validity()` → cheap JSON probe at `/mosaiques/METROPOLE/observations/LAME_D_EAU` to get the freshest `validity_time`.
   b. Compare against `manifest.most_recent_timestamp("radar")` — if equal, exit without download.
   c. `fetch_latest_radar(dest)` → HTTP GET the HDF5 produit (~2 MB) into `sources/radar/<ts>.h5`.
   d. `manifest.upsert_layer_frame` adds the timestamp to `layers.radar.frames`, idempotent.
   e. `manifest.write_manifest` atomic write of `manifest.json`.

3. Later, when a client first requests `/radar/<ts>/<z>/<x>/<y>.png`:
   a. Caddy's `file` matcher misses (`cache/...` doesn't exist).
   b. Caddy reverse-proxies to `127.0.0.1:8765`.
   c. Tile server: `_get_source` (LRU memo, last 8) loads `sources/radar/<ts>.h5` via `radar_hdf5.read_mosaic`.
   d. `tiles.render_tile_projected` computes the tile's lat/lon corners, transforms them into the radar's polar-stereographic CRS via `pyproj`, samples the source array bilinearly with `scipy.ndimage.map_coordinates`, colourises with `colormap.colorize`.
   e. Atomic write to `cache/radar/<ts>/<z>/<x>/<y>.png` (mode 0644 so Caddy can read it).
   f. Returns the PNG bytes.

The forecast cycle (`ingest-arome`) is similar but loops over 24 lead-time GRIB2s and tolerates 404s (AROME-PI publishes leadtimes incrementally — the next cycle tops up the missing ones).

## Key design choices

- **Schema-as-contract.** `schema/manifest.schema.json` (v2) is the contract; both backend and client validate against it. CI re-validates on every PR. Manifest v2 ships per-layer `tileUrlTemplate` + `minZoom`/`maxZoom` + a list of available frame timestamps; no per-frame URL.
- **Lazy XYZ tile pyramid.** Sources cached on disk; tiles rendered on first request and cached. See ADR-0004.
- **Atomic writes everywhere.** `manifest.write_manifest`, `render.write_png`, `tile_server._write_atomic` all do `*.tmp` → `chmod 0644` → `os.replace`.
- **Source-cache LRU.** Tile server keeps the 8 most recently used `(layer, ts)` source objects in memory to avoid re-decoding for every tile.
- **CRS handling.** AROME-PI WCS already returns EPSG:4326 lat/lon — `tiles.render_tile_lonlat` uses `np.interp` for index lookup. DPRadar HDF5 is on a polar-stereographic 500 m grid — `tiles.render_tile_projected` uses `pyproj.Transformer` (EPSG:4326 → source CRS) for each tile's pixel grid.

## Where the code lives

| Concern | File |
|---|---|
| HTTP clients for both MF APIs | `backend/src/radar/meteofrance.py` |
| AROME-PI GRIB parsing | `backend/src/radar/grib.py` |
| DPRadar HDF5 parsing | `backend/src/radar/radar_hdf5.py` |
| XYZ tile geometry + per-tile rendering | `backend/src/radar/tiles.py` |
| Lazy tile-rendering HTTP service | `backend/src/radar/tile_server.py` |
| Reprojection grid builders | `backend/src/radar/reproject.py` |
| mm/h → RGBA color ramp | `backend/src/radar/colormap.py` |
| Atomic PNG writer | `backend/src/radar/render.py` |
| Manifest read/write/validate (v2) | `backend/src/radar/manifest.py` |
| Retention (sources + cache + manifest pruning) | `backend/src/radar/retention.py` |
| CLI entrypoint | `backend/src/radar/cli.py` |
| systemd units | `backend/systemd/*.service`, `*.timer` |
| Caddy config (prod + dev) | `backend/caddy/Caddyfile`, `Caddyfile.dev` |
| Deploy scripts | `backend/deploy/{install,update}.sh` |

## ADRs

- [ADR-0001 — Monorepo](adr/0001-monorepo.md)
- [ADR-0002 — No Python web framework](adr/0002-no-python-web-framework.md) — *partially superseded*
- [ADR-0003 — KMP with per-platform MapLibre via expect/actual](adr/0003-kmp-with-expect-actual-map.md)
- [ADR-0004 — Lazy XYZ tile server](adr/0004-lazy-tile-server.md)
