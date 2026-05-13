# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A self-hosted, RainViewer-style precipitation-radar app covering all of metropolitan France (incl. Corsica). Météo-France DPRadar mosaic (observed, 500 m, every 5 min) + pysteps optical-flow nowcast (0–60 min) + Météo-France AROME-PI (0–6 h forecast, ~1.1 km, hourly runs). Backend runs on a Hetzner VPS at `178.104.157.63`, private (HTTP basic auth + per-user rate limit), trusted-friends scale.

**Implementation status (Phases 1 + 2 complete; iOS deferred):**
- ✅ Real ingest of both Météo-France APIs (`meteofrance.py` fully wired, `radar_hdf5.py` reads + writes ODIM_H5, `grib.py` parses AROME-PI GRIB2).
- ✅ Lazy XYZ tile rendering (`tile_server.py` FastAPI service, `tiles.py` math + render helpers).
- ✅ Manifest v2 schema (tileUrlTemplate + minZoom/maxZoom + per-layer frame list; no per-frame URL).
- ✅ Auto-deploy on push to `main` (GitHub Actions SSHs to VPS).
- ✅ `radar nowcast` runs pysteps optical-flow extrapolation on the last 4 radar frames, writes 12 predicted ODIM_H5 frames to `sources/nowcast/`, replaces the cache + manifest on each run. Logs + exits 0 if `pysteps` isn't installed.
- ✅ **Phase 2 — Kotlin client**: Android (`MapView` + `RasterSource` with OkHttp basic-auth interceptor) and Wasm (`maplibre-gl-js` with `transformRequest`) both wire the manifest's `tileUrlTemplate`. First-launch flow prompts for password (URL baked in `Config.BASE_URL`), persists to platform settings, polls `manifest.json` every 60 s, builds a unified chronological timeline (radar → nowcast → forecast) and drives a `TimelineScrubber`. Wasm layout splits the viewport: map on top, fixed 320 px Compose canvas at bottom for the auth sheet + timeline card.
- ⏳ **iOS** stays placeholder — needs macOS + Xcode to link the framework; revisit when Mac access is available.

## Common commands

The top-level `Makefile` is the canonical entry point. Run from repo root.

```
make help                # list targets
make setup               # install uv + download Gradle wrapper jar (one-off)
make backend-sync        # uv sync (Python deps; FastAPI/uvicorn included)
make backend-test        # pytest
make backend-lint        # ruff check
make backend-cli         # `radar --help` smoke test
make schema-validate     # check-jsonschema example against the manifest schema
make client-android      # ./gradlew :androidApp:assembleDebug
make client-wasm         # ./gradlew :wasmJsApp:wasmJsBrowserDevelopmentRun
make client-test         # ./gradlew :shared:allTests
```

Single-test runs:

```
cd backend && uv run pytest tests/test_manifest.py::test_validation_rejects_bad_version
cd client  && ./gradlew :shared:wasmJsTest --tests "*ManifestSchemaConsistencyTest"
```

`pysteps` is an **optional extra** (compiles C extensions, needs `python3.12-dev` + `libeccodes-dev`). Install with `cd backend && uv sync --extra nowcast`. Base install deliberately works without it so CI / dev boxes stay simple.

Backend uses `uv` (not pip/poetry). Tooling lives on `$HOME/.local/bin` after `make setup`; on Linux, also `source $HOME/.sdkman/bin/sdkman-init.sh` for Java 21 in fresh shells.

**Code changes always flow through GitHub** — never edit code on the VPS directly. Edit locally, `git push`, then either let the auto-deploy fire on `main` or trigger it manually with `gh workflow run deploy-backend.yml` / `ssh root@178.104.157.63 'sudo /opt/radar/backend/deploy/update.sh'`. Ad-hoc inspection scripts under `/tmp/` on the VPS are fine and don't need to be checked in.

## Big-picture architecture

### Three trees, one contract

```
schema/      JSON Schema 2020-12, manifest v2 — sole contract
backend/     Python ingest + FastAPI tile server + ops
client/      Kotlin Multiplatform app (Compose Multiplatform UI)
```

`schema/manifest.schema.json` is the contract between backend and clients. Backend validates every write (`radar.manifest.validate_manifest`); the client decodes `schema/examples/manifest.example.json` in `ManifestSchemaConsistencyTest`. **Always update both sides together** — the three workflows in `.github/workflows/` (schema/backend/client) all re-validate.

### Backend: split into ingest + tile server

The backend has **two layers**:

**1. Ingest (one-shot CLI scripts on systemd timers)** — `cli.py` Typer commands map 1:1 to systemd units in `backend/systemd/`:

| Subcommand          | Timer cadence                     | Job |
|---------------------|-----------------------------------|---|
| `radar ingest-radar`| `*:0/5:30` (every 5 min, :30s)    | Download latest DPRadar mosaic HDF5 to `sources/radar/<ts>.h5`, update manifest |
| `radar nowcast`     | `*:2/5:30` (every 5 min, offset)  | Run pysteps LK on the last 4 radar frames, write 12 predicted ODIM_H5 frames to `sources/nowcast/`, update manifest |
| `radar ingest-arome`| `*:10:00` (hourly at HH:10)       | Download all available AROME-PI leadtime GRIB2s to `sources/forecast/<ts>.grib2`, update manifest |
| `radar cleanup`     | `03:30` daily                     | Drop sources older than retention + their cached tile trees |

**2. Tile server (long-running)** — `radar tile-server` (FastAPI + uvicorn, loopback `127.0.0.1:8765`, `radar-tileserver.service`). Caddy reverse-proxies tile requests to it on cache miss. The server:
1. Loads the cached source for `(layer, timestamp)` from `sources/<layer>/<ts>.{h5,grib2}` (memoised, last 8 LRU)
2. Computes the requested tile's bbox in Web Mercator
3. Reprojects + colourises the 256×256 tile (using `tiles.py` helpers)
4. Saves the PNG atomically to `cache/<layer>/<ts>/<z>/<x>/<y>.png`
5. Returns the PNG bytes

Caddy's `file` matcher checks the cache directory first; cache hit → pure static serving (sub-50 ms), cache miss → reverse_proxy. The tile server only runs on cache misses.

See `docs/adr/0004-lazy-tile-server.md` for the architectural reasoning.

Data layout on the VPS:
```
/var/lib/radar/tiles/
├── manifest.json                          # v2; clients read this
├── sources/                               # raw source files (private)
│   ├── radar/<YYYY-MM-DDTHH-MM-SSZ>.h5
│   └── forecast/<YYYY-MM-DDTHH-MM-SSZ>.grib2
└── cache/                                 # lazy-rendered tiles (Caddy serves)
    ├── radar/<ts>/<z>/<x>/<y>.png
    ├── nowcast/<ts>/<z>/<x>/<y>.png
    └── forecast/<ts>/<z>/<x>/<y>.png
```

### Météo-France APIs

Two subscriptions on <https://portail-api.meteofrance.fr/>, one apikey each (both in `/etc/radar/env`):

- **AROME-PI** — `https://public-api.meteofrance.fr/public/aromepi/1.0/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS` (WCS 2.0.1). Forecast 0–6 h at 15-min steps. Native EPSG:4326 lat/lon, 0.01° (~1.1 km). GRIB short-name `tirf`, unit `kg m⁻²` over the 15-min window. **WCS quirk**: `subset=time(VALUE)` (slice) is mandatory; trim (`time(low,high)`) is rejected.
- **DPRadar** — `https://public-api.meteofrance.fr/public/DPRadar/v1`. REST, HATEOAS-style. Use `/mosaiques/METROPOLE/observations/LAME_D_EAU/produit?maille=500` for HDF5 (`maille=1000` gives gzipped BUFR — avoid). Native polar-stereographic (ODIM_H5), 3472×3472 at 500 m. The descriptor at `/mosaiques/METROPOLE/observations/LAME_D_EAU` carries `validity_time` — cheap dedup probe before pulling the 2 MB file.

See `docs/data-sources.md` for the full discovery log (coverage IDs, projdef strings, response shapes).

**AROME-PI publishes leadtimes incrementally** over the hour following its run reference time. `fetch_arome_leadtime` returns `None` on HTTP 404 (= leadtime not yet published, not retried). `ingest-arome` distinguishes:
- **New run**: rmtree forecast/ sources + cache, fetch every available leadtime
- **Same run, partial**: top up only the leadtimes whose source isn't already on disk

This is intentional and load-bearing — don't simplify it back to a single hot-loop fetch.

### Reprojection

`reproject.py` has two grid builders:
- `build_grid` — regular lat/lon source (used by AROME-PI WCS output, already EPSG:4326)
- `build_proj_grid` — arbitrary projected source CRS (used by DPRadar's polar-stereographic ODIM_H5)

Both produce a `ReprojectionGrid` that `tiles.py` consumes for per-tile sampling. The tile server builds these per-request (per-tile, 256×256); the original "build once at startup" pattern from the pre-render era is gone.

### Client: KMP + Compose, map per platform

Everything except the map view lives in `client/shared/src/commonMain/`. The map is a single `expect`:

```kotlin
@Composable
expect fun RadarMap(
    bbox: Bbox,
    currentFrame: TimelineFrame?,
    tileAuthHeader: String,
    modifier: Modifier = Modifier,
)
```

[TimelineFrame] carries `tileUrlTemplate` with `{timestamp}` already substituted (URL-safe `YYYY-MM-DDTHH-MM-SSZ` form matching the backend's source/cache directory layout). MapLibre fills the remaining `{z}/{x}/{y}` per tile fetch.

Two actuals are wired; iOS is placeholder:
- **Android** — `AndroidView { MapView }` from `org.maplibre.gl:android-sdk` (11.x). `MapLibre.getInstance(context)` initialises the singleton from the `AndroidView.factory`; `HttpRequestUtil.setOkHttpClient(client)` installs an interceptor that attaches `Authorization: Basic …` only to requests whose path starts with `/radar/`, `/nowcast/`, or `/forecast/` — the demotiles base map fetches stay unauthenticated. Lifecycle (`onStart/onStop/onPause/onResume/onDestroy`) is forwarded via `LifecycleEventObserver` on `LocalLifecycleOwner`.
- **Wasm** — `maplibre-gl-js` mounted on a `<div id="map">` declared in `wasmJsApp/src/wasmJsMain/resources/index.html`. The Compose canvas is sized to a 320 px strip at the bottom of the viewport; the map fills the rest. The map is NOT inside the Compose tree — `RadarMap.wasmJs.kt` is a side-effect-only composable that runs `DisposableEffect` to create/destroy the JS map and `LaunchedEffect` to swap the radar `RasterSource`'s tile list when `currentFrame` changes. JS interop uses `@JsFun` strings (no separate `.d.ts` shim). The same conditional-auth `transformRequest` is applied at map construction.
- **iOS** — placeholder. The `UIKitView { MGLMapView }` wiring needs macOS + Xcode to actually link.

**First-launch flow** (commonMain `RadarScreen`): if `SettingsStore` has no `auth.password`, show `AuthSheet` (username + password fields). On submit, persist to settings, build an Ktor `HttpClient` with Basic auth, kick off `RadarRepository.pollManifest(60s)`. Each new manifest is flattened by `Manifest.toTimeline(baseUrl)` into a single chronological list of `TimelineFrame`s spanning radar → nowcast → forecast. The slider drives `currentIndex`; tapping `⎋` clears creds and re-shows the auth sheet.

`Config.BASE_URL` is the only build-time configuration (defaults to `https://rain.axl-lvy.fr/`). Edit + rebuild to point at a different backend.

KMP **source-set layout v2** is in effect: Kotlin sources, `AndroidManifest.xml`, and `res/` all live under `src/androidMain/` (not `src/main/`). `expect/actual` classes are in Kotlin Beta — `kotlin.mpp.expectActualClasses=true` in `gradle.properties` acknowledges that and silences the warning.

The Gradle wrapper jar is **not committed**; `setup.sh` downloads it from the official Gradle distribution. The Android SDK location is in `client/local.properties` (also not committed).

Package namespace is `eu.yourname.radar.*` — placeholder, rename when claiming a real domain.

### iOS

iOS targets cross-compile from Linux for the metadata pass, but linking the framework and building the `iosApp` Xcode project **requires macOS + Xcode**. `client/iosApp/` ships Swift entry-point files and a README with XcodeGen instructions; no `.xcodeproj` is checked in. On Linux, Gradle skips the iOS link tasks with a warning (suppressed via `kotlin.native.ignoreDisabledTargets=true`).

### CI and auto-deploy

Four workflows in `.github/workflows/`, all path-filtered + each with `workflow_dispatch`:

- `schema.yml` — `schema/**` — validates the example against the schema.
- `backend.yml` — `backend/**` or `schema/**` — installs `libeccodes-dev`, `uv sync`, ruff, pytest, schema check.
- `client.yml` — `client/**` or `schema/**` — `:shared:allTests`, Android debug APK, Wasm distribution bundle.
- `deploy-backend.yml` — `workflow_run` of `backend` finishing on `main` + manual `workflow_dispatch`. SSHs in as `deploy` (secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, optional `DEPLOY_PORT`) and runs `sudo /opt/radar/backend/deploy/update.sh`. Requires a GitHub Environment named `production`.

`update.sh` does **not** touch `/etc/radar/env` (secrets) or `/etc/caddy/Caddyfile` (user passwords). Those are edited manually on the VPS and survive deploys. `update.sh` does restart `radar-tileserver.service` so it picks up new code.

The `rate_limit` directive in `backend/caddy/Caddyfile` is **not** in the stock Caddy build — install.sh runs `caddy add-package github.com/mholt/caddy-ratelimit` (works on the Cloudsmith .deb install).

`workflow_run` only fires from the **default branch's** copy of the workflow file. Editing `deploy-backend.yml` on a feature branch won't trigger; merge to `main` first.

### Local development

`dev/fake-data.py` and `dev/Caddyfile.dev` predate the v2 schema migration and **don't work end-to-end against v2** (fake-data emits v1 frames with `url` fields). Updating them is a backlog task. For now, **develop against the live VPS** — it's the only working environment.

When the local-dev path is revived: `dev/Caddyfile.dev` is already updated to the lazy pattern (cache-then-render via `host.docker.internal:8765`), so the missing piece is `fake-data.py` producing source files (or pre-rendered tiles in `cache/`).

## Conventions and pitfalls worth remembering

- **Code changes always flow through GitHub.** Never edit `/opt/radar/...` on the VPS directly; always edit local → push → pull/auto-deploy. Ad-hoc `/tmp/` exploration scripts on the VPS don't need committing.
- **Conventional Commits.** No Claude `Co-Authored-By` trailer (user preference).
- **Time and filenames are UTC ISO-8601 end-to-end.** Source files and cache tile dirs use the URL-safe form `YYYY-MM-DDTHH-MM-SSZ` (colons → dashes). Convert to local time only at display.
- **Manifest version is now 2.** Older v1 manifests are rejected on read by `_load_or_init_manifest` and rebuilt fresh. Bump to v3 only on truly breaking changes; additive fields keep v2.
- **Atomic writes everywhere.** `manifest.write_manifest`, `render.write_png`, and `tile_server._write_atomic` all write to `*.tmp` then `os.replace`. Files come out mode 0644 so the `caddy` user can read what the `radar` user writes. Preserve this in any new writer.
- **404 from AROME-PI on a leadtime is "not yet published", not "broken".** `fetch_arome_leadtime` returns `None`; the loop in `fetch_arome_run` skips it. The next ingest cycle tops up.
- **DPRadar `/mosaiques/.../observations/LAME_D_EAU` JSON descriptor exposes `validity_time`** — use it as a cheap dedup probe before pulling the heavy `produit` file.
- **The tile server caches sources in memory (last 8 LRU)** but tile PNGs always live on disk — restarting the server is loss-free.
- **`pysteps` install needs `python3.12-dev` + `libeccodes-dev`** — that's why it's an extra; base `uv sync` deliberately stays compilable on stripped-down dev boxes and CI.
- **Don't recompute reprojection grids per tile if you can cache.** Currently the tile server does compute per-tile (it's cheap and correct); if profiling shows it's a bottleneck, memoise by `(layer, z, x, y)` on the tile server.

## ADRs

1. [ADR-0001 — Monorepo](docs/adr/0001-monorepo.md)
2. [ADR-0002 — No Python web framework](docs/adr/0002-no-python-web-framework.md) — *partially superseded by ADR-0004*
3. [ADR-0003 — KMP with per-platform MapLibre via expect/actual](docs/adr/0003-kmp-with-expect-actual-map.md)
4. [ADR-0004 — Lazy XYZ tile server](docs/adr/0004-lazy-tile-server.md)
