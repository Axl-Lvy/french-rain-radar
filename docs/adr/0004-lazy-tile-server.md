# ADR 0004 — Lazy XYZ tile server

**Status:** Accepted (supersedes part of [ADR 0002](0002-no-python-web-framework.md))
**Date:** 2026-05-13

## Context

The product expanded from a single small bbox (Apt/Avignon) to all of metropolitan France with the explicit requirement that users can zoom to their own location and see sharp rain. A single PNG per frame covering France would be blocky at city-level zoom; pre-rendering a full XYZ pyramid at z=5..9 would render ~1400 tiles per frame whether anyone looks at them or not.

## Decision

- The backend ingest still runs on systemd timers and pulls Météo-France data, but it **only saves the source files** (HDF5 / GRIB) to `tile_dir/sources/<layer>/<ts>.{h5,grib2}` — no tile rendering at ingest time.
- A small **FastAPI tile-renderer** (`radar tile-server`) runs as a long-lived systemd service on loopback `127.0.0.1:8765`. It handles `/{layer}/{timestamp}/{z}/{x}/{y}.png` requests: loads the cached source for `(layer, timestamp)`, reprojects + colourises the requested tile, writes it to `tile_dir/cache/<layer>/<ts>/<z>/<x>/<y>.png`, and returns the bytes.
- **Caddy** matches tile paths and uses its `file` matcher: cache hit → serve the static PNG directly (the fast path); cache miss → `reverse_proxy` to the tile server.
- The manifest (v2 schema) carries per-layer `tileUrlTemplate`, `minZoom`, `maxZoom` plus a list of available timestamps; no per-frame URL.

## Consequences

**Positive**

- Tiles are rendered only for what users actually request, saving CPU and disk on the cheap VPS.
- No `max_zoom` cap pre-baked into the backend — the server renders any zoom the client asks for (the source's intrinsic resolution is the real limit).
- Cache hits are still pure-static (Caddy `file_server`), so latency stays sub-50 ms for already-viewed tiles.
- The ingest path becomes simpler: download + save + bump manifest, no rendering.

**Negative**

- Adds a Python long-running service to the system (revising ADR 0002's "no Python web framework" stance). The service is small (~200 lines) and entirely behind Caddy, but it's another moving part to babysit.
- First request to an unrendered tile pays a render cost (~50–300 ms). Acceptable for the trusted-friends scale; would be a concern at scale.

## Alternatives considered

- **Pre-render the full pyramid every cycle.** Discarded — the user explicitly cares about CPU-frugal operation on a cheap VPS, and the bulk of rendered tiles are over ocean / off-AOI / never viewed.
- **Render to a single very-large PNG (4096×4096 or larger).** Discarded — still blocky past z=8 and wastes bandwidth shipping the full image when only a small portion is viewed.
- **Vector tiles.** Discarded — the data is fundamentally raster (precipitation field); vectorisation would lose information.
