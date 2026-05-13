# french-rain-radar

A self-hosted precipitation-radar app focused on France (primarily the Apt / Avignon region), modelled after RainViewer's Pro tier. Free Météo-France data; private deployment for trusted users.

## What this is

- **Observed radar** every 5 min at ~1 km resolution (Météo-France radar mosaic).
- **0–60 min nowcast** via pysteps optical-flow extrapolation on the radar history.
- **1–6 h forecast** from Météo-France AROME-NWC.
- Animated overlay on a MapLibre map, delivered to Android, iOS, and Web (Wasm) clients from a single Kotlin Multiplatform codebase.

## Repository layout

```
schema/     # JSON Schema for the manifest contract — single source of truth
backend/    # Python pipeline + Caddy + systemd units (runs on a Hetzner VPS)
client/     # Kotlin Multiplatform app (Android, iOS, WasmJS) via Compose Multiplatform
docs/       # Architecture notes and ADRs
dev/        # Local-dev tooling: fake data generator, docker-compose for Caddy
tools/      # Misc helpers used by CI
```

## Quick start (local dev)

```bash
# 1. One-off bootstrap (installs uv and the Gradle wrapper)
./setup.sh

# 2. Generate fake tile data + manifest so the client has something to display
make fake-data

# 3. Serve the tile directory locally on http://localhost:8080  (basic auth: dev / dev)
make dev-caddy

# 4. Build the Android app  (requires JDK 21 + Android SDK)
make client-android

# 5. Run the Wasm app in your browser
make client-wasm
```

See [`docs/architecture.md`](docs/architecture.md) for the full picture and [`dev/README.md`](dev/README.md) for offline development against fake data.

## Production deployment

See [`docs/deployment.md`](docs/deployment.md) and [`backend/deploy/README.md`](backend/deploy/README.md).

## License

TBD — pick one before publishing. AGPL-3.0 is a reasonable default for self-hosted services.
