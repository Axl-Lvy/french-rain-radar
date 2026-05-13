# Architecture

## One-paragraph summary

A Python pipeline runs on a Hetzner VPS, pulls radar and AROME-NWC data from Météo-France every few minutes, reprojects each grid to Web Mercator for the Apt/Avignon bounding box, renders coloured PNGs, and atomically updates a `manifest.json` describing the available frames. Caddy serves the PNGs and manifest over HTTPS behind Basic Auth + per-user rate limiting. A Kotlin Multiplatform client (Android, iOS, WasmJS) polls the manifest, overlays the PNGs on a MapLibre map, and animates the timeline.

## Data flow

```
                ┌──────────────────────────────┐
                │  Météo-France open-data API   │
                │  (radar mosaic + AROME-NWC)   │
                └─────────────┬─────────────────┘
                              │ GRIB2
                              ▼
   ┌──────────────────────────────────────────────────┐
   │  backend/ (Python, systemd timers)               │
   │                                                  │
   │   ingest-radar  (every 5 min)  ──┐               │
   │   nowcast       (every 5 min)  ──┼─► PNG + JSON  │
   │   ingest-arome  (hourly)       ──┘               │
   │   cleanup       (daily)                           │
   └────────────────────────┬─────────────────────────┘
                            │ filesystem
                            ▼
              /var/lib/radar/tiles/
                ├── manifest.json
                ├── radar/<ts>.png
                ├── nowcast/<ts>.png
                └── forecast/<ts>.png
                            │
                            ▼
                   ┌──────────────────┐
                   │  Caddy           │
                   │  - HTTPS         │
                   │  - basic_auth    │
                   │  - rate_limit    │
                   └────────┬─────────┘
                            │ HTTPS
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Android        iOS           Wasm
                  (Kotlin Multiplatform client)
```

## Key design choices

- **No Python web framework.** The "API" is `manifest.json` + a directory of PNGs. Caddy serves static files directly.
- **Schema-as-contract.** The manifest schema in `schema/` is checked by both backend (on write) and client (on read) so they can never drift.
- **One pipeline, three layers.** Observed radar comes from Météo-France, the 0–60 min nowcast is extrapolated locally with pysteps, the 1–6 h forecast comes from AROME-NWC. They share a manifest with three `layers`.
- **Fixed bounding box.** Render only the Apt/Avignon region. No global tile pyramid.
- **Web Mercator output.** GRIBs are in Lambert-93 (EPSG:2154); rendered PNGs are in Web Mercator (EPSG:3857) so MapLibre can overlay them without further work.

## Sequence: one ingestion cycle

1. `radar-ingest.timer` triggers `radar ingest-radar`.
2. Fetch the latest radar-mosaic GRIB from Météo-France.
3. Open with `xarray` + `cfgrib`, slice to bounding box, reproject to Web Mercator via a precomputed `pyproj` grid.
4. Colourise the precipitation field (`colormap.py`).
5. Write `radar/<timestamp>.png` to a temp file, `os.replace` into place.
6. Update `manifest.json` atomically: load → mutate `layers.radar.frames` → write to `manifest.json.tmp` → rename.
7. Old PNGs are deleted by `radar-cleanup.timer` (daily, keeps last N hours).

## Why this stack

See:
- [`adr/0001-monorepo.md`](adr/0001-monorepo.md)
- [`adr/0002-no-python-web-framework.md`](adr/0002-no-python-web-framework.md)
- [`adr/0003-kmp-with-expect-actual-map.md`](adr/0003-kmp-with-expect-actual-map.md)
