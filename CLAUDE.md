# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A self-hosted, RainViewer-style precipitation-radar app focused on the Apt / Avignon region of France. Météo-France radar mosaic (observed) + pysteps optical-flow nowcast (0–60 min) + AROME-NWC (1–6 h forecast) → coloured PNG tiles served by Caddy → animated map overlay in a Kotlin Multiplatform client (Android, iOS, WasmJS). Backend runs on a Hetzner VPS, private (basic auth + per-user rate limit), trusted-friends scale.

The scaffold is committed; the data-fetch and nowcast modules (`backend/src/radar/{meteofrance,grib,nowcast}.py`) are stubs marked with `raise NotImplementedError`. Everything around them (colormap, render, manifest read/write/validate, retention, CLI, reprojection) is real and unit-tested. Local development runs against synthetic data from `dev/fake-data.py`, so the client can be exercised without Météo-France credentials.

## Common commands

The top-level `Makefile` is the canonical entry point — prefer it over remembering tool incantations.

```
make help                # list targets
make setup               # install uv + download Gradle wrapper jar (one-off)
make backend-sync        # uv sync (Python deps)
make backend-test        # pytest
make backend-lint        # ruff check (with --fix variant via `uv run ruff check . --fix`)
make backend-cli         # `radar --help` smoke test
make fake-data           # generate synthetic PNGs + manifest into dev/data/tiles/
make dev-caddy           # docker compose up local Caddy on :8080 (auth: dev/dev)
make dev-stack           # fake-data + dev-caddy in one step
make client-android      # ./gradlew :androidApp:assembleDebug
make client-wasm         # ./gradlew :wasmJsApp:wasmJsBrowserDevelopmentRun
make client-test         # ./gradlew :shared:allTests
make schema-validate     # check-jsonschema example against the manifest schema
```

Single-test runs:

```
cd backend && uv run pytest tests/test_manifest.py::test_validation_rejects_bad_version
cd client  && ./gradlew :shared:wasmJsTest --tests "*ManifestSchemaConsistencyTest"
```

`pysteps` is an **optional extra** because it compiles C extensions and needs `python3.12-dev` + `libeccodes-dev` at build time. Install it on a machine with those headers via `cd backend && uv sync --extra nowcast`. Without it, only `radar nowcast` fails; everything else works.

Backend uses `uv` (not pip/poetry). Tooling lives on `$HOME/.local/bin` after `make setup`; on Linux, also `source $HOME/.sdkman/bin/sdkman-init.sh` for Java 21 in fresh shells.

## Big-picture architecture

### Three trees, one contract

```
schema/      single source of truth (JSON Schema 2020-12) — manifest.schema.json
backend/     Python pipeline + ops (systemd, Caddy, deploy scripts)
client/      Kotlin Multiplatform app (Compose Multiplatform for UI)
```

`schema/manifest.schema.json` is the contract between backend and clients. The backend validates every write against it (`radar.manifest.validate_manifest`); the client decodes `schema/examples/manifest.example.json` into the Kotlin model in `ManifestSchemaConsistencyTest`. **If you change one side, change both** — `.github/workflows/schema.yml`, `backend.yml`, and `client.yml` each re-validate.

### Backend: deliberately not a web framework

The backend is a set of one-shot CLI scripts triggered by systemd timers. They write PNG tiles + a `manifest.json` atomically to `RADAR_TILE_DIR`. Caddy serves that directory as static files. There is no FastAPI / Flask / aiohttp, and there shouldn't be — see `docs/adr/0002-no-python-web-framework.md`.

The CLI lives in `backend/src/radar/cli.py` (Typer). Each subcommand maps **1:1** to a systemd unit under `backend/systemd/`:

| Subcommand          | Timer                  | Cadence       |
|---------------------|------------------------|---------------|
| `radar ingest-radar`| `radar-ingest.timer`   | every 5 min   |
| `radar nowcast`     | `radar-nowcast.timer`  | every 5 min, offset |
| `radar ingest-arome`| `arome-ingest.timer`   | hourly `HH:05`|
| `radar cleanup`     | `radar-cleanup.timer`  | daily `03:30` |

If you add a subcommand, add the matching `.service` + `.timer`.

**Atomic-write discipline** is load-bearing: clients must never observe a half-written file. `radar.manifest.write_manifest` and `radar.render.write_png` both write to `*.tmp` then `os.replace()`; preserve that pattern in any new writer.

Data flow inside one ingestion cycle:

```
Météo-France GRIB2
   → cfgrib/xarray (radar.grib.read_precip)
   → Lambert-93 → Web Mercator via precomputed pixel mapping (radar.reproject)
   → mm/h → RGBA colormap (radar.colormap.colorize)
   → PNG via Pillow (radar.render.write_png)
   → manifest update (radar.manifest.write_manifest)
```

`radar.reproject.build_grid` precomputes the pixel→source-grid mapping **once** at startup; don't recompute per-frame. Bounding box and tile dimensions come from `RADAR_BBOX_*` / `RADAR_TILE_*` env vars; see `backend/deploy/env.example`.

### Client: KMP + Compose, map view per platform

Everything except the map view lives in `client/shared/src/commonMain/`. The map is declared once:

```kotlin
@Composable
expect fun RadarMap(bbox: Bbox, overlayUrl: String?, modifier: Modifier = Modifier)
```

Three actuals: Android (`AndroidView { MapView }` from `org.maplibre.gl:android-sdk`), iOS (`UIKitView { MGLMapView }` via cinterop), Wasm (HTMLElement hosting maplibre-gl-js). All three currently render a placeholder Box — replacing them with real MapLibre wiring is the first real client task.

KMP **source-set layout v2** is in effect: Kotlin sources live under `src/<target>Main/kotlin/`, not `src/main/kotlin/`. AGP still owns `src/main/AndroidManifest.xml` and `src/main/res/`.

`expect/actual` classes are in Kotlin Beta — `kotlin.mpp.expectActualClasses=true` in `client/gradle.properties` acknowledges this and silences the warning.

The Gradle wrapper jar is **not committed** (it's binary). `setup.sh` downloads it from the official Gradle distribution. The version is pinned in `setup.sh` and `client/gradle/wrapper/gradle-wrapper.properties`.

Package namespace is `eu.yourname.radar.*` — placeholder, rename across the tree when claiming a real domain.

### iOS

iOS targets cross-compile from Linux for the metadata pass, but linking the framework and building the `iosApp` Xcode project **requires macOS + Xcode**. `client/iosApp/` ships Swift entry-point files and a README with XcodeGen instructions; no `.xcodeproj` is checked in. On Linux, Gradle skips the iOS link tasks with a warning (suppressed via `kotlin.native.ignoreDisabledTargets=true`).

### CI and auto-deploy

Four workflows in `.github/workflows/`, all path-filtered:

- `schema.yml` — `schema/**` — validates the example against the schema.
- `backend.yml` — `backend/**` or `schema/**` — installs `libeccodes-dev`, `uv sync`, ruff, pytest, schema check.
- `client.yml` — `client/**` or `schema/**` — `:shared:allTests`, Android debug APK, Wasm distribution bundle.
- `deploy-backend.yml` — triggered by `workflow_run` of `backend` on `main`, SSHs to the VPS as the `deploy` user (secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, optional `DEPLOY_PORT`) and runs `sudo /opt/radar/backend/deploy/update.sh`. Requires a GitHub Environment named `production`.

`update.sh` deliberately does **not** touch `/etc/radar/env` (secrets) or `/etc/caddy/Caddyfile` (user passwords). Those live on the VPS only.

The `rate_limit` directive in `backend/caddy/Caddyfile` is **not** in the stock Caddy build — the VPS binary must be built with `github.com/mholt/caddy-ratelimit` via `xcaddy`. See `backend/deploy/README.md`.

`workflow_run` only fires from the **default branch's** copy of the workflow file. Editing `deploy-backend.yml` on a feature branch won't make it trigger; it must be on `main`.

### Local development against synthetic data

`dev/fake-data.py` generates a 24-frame radar history + 12-frame nowcast + 6-frame forecast for the Apt bbox using a moving Gaussian blob, then writes a valid `manifest.json`. `dev/docker-compose.yml` runs `caddy:2-alpine` with `backend/caddy/Caddyfile.dev` (HTTP, port 8080, basic auth `dev`/`dev`) serving `dev/data/tiles/`.

Client base URLs against the local stack:

| Target | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8080` |
| iOS simulator / Wasm | `http://localhost:8080` |
| Physical device on LAN | your host IP, e.g. `http://192.168.1.42:8080` |

## Conventions and pitfalls worth remembering

- **Conventional Commits.** No Claude `Co-Authored-By` trailer (user preference).
- **Time and filenames are UTC ISO-8601 end-to-end.** PNG filenames use `YYYY-MM-DDTHH-MM-SS.png` (colons swapped to dashes for cross-platform safety). Convert to local time only at the display layer.
- **Bump `manifestVersion` when removing/renaming fields**; additive changes keep version 1. Clients reject unknown versions cleanly.
- **Don't add a Python web framework.** ADR-0002 captures the why.
- **Don't recompute the reprojection grid per frame.** It's invariant once the bbox and tile size are set.
- **Don't mock the schema in tests.** Round-trip `schema/examples/manifest.example.json` so any drift is caught.
- **`pysteps` install can fail on machines without `python3.12-dev` + `libeccodes-dev`.** That's why it's an extra; base `uv sync` deliberately stays compilable on stripped-down dev boxes and CI.
- **Météo-France API endpoints in `meteofrance.py` are unverified placeholders.** Confirm against the current docs at `https://portail-api.meteofrance.fr/` before relying on them.
