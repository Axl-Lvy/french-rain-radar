# french-rain-radar

A self-hosted precipitation-radar app covering all of metropolitan France (including Corsica), modelled after RainViewer's Pro tier. Free Météo-France data, private deployment for trusted users, deep zoom anywhere on the map.

## What this is

- **Observed radar** every 5 min at 500 m resolution (Météo-France DPRadar mosaic, ODIM_H5).
- **0–6 h forecast** at 15-min steps, ~1.1 km resolution (Météo-France AROME-PI, GRIB2).
- **0–60 min nowcast** via pysteps optical-flow extrapolation on the radar history *(scaffolded; wiring is the last Phase 1 task)*.
- **Lazy XYZ tile pyramid**: a small Python tile server renders 256×256 PNG tiles on demand the first time a client requests them, and Caddy serves them statically thereafter. Clients can zoom to any neighbourhood and the right tiles are produced at request time.
- **Animated overlay** on a MapLibre map, delivered to Android, iOS, and Web (Wasm) clients from a single Kotlin Multiplatform / Compose Multiplatform codebase.

## Architecture (one paragraph)

A Python ingest pipeline runs on a Hetzner VPS, pulls radar + AROME-PI data from Météo-France every 5 min / hour (systemd timers), and only **saves the raw source files** (HDF5, GRIB2) to disk. A FastAPI tile server (`radar-tileserver.service`, on `127.0.0.1:8765`) handles tile requests on cache miss: it loads the cached source, reprojects + colourises the requested 256×256 tile, writes the PNG to disk, and returns it. **Caddy** fronts everything with HTTPS, HTTP basic auth, and per-user rate limiting; its `file` matcher serves cache hits as pure static (sub-50 ms) and reverse-proxies cache misses to the tile server. The client polls the **`manifest.json`** for available frame timestamps and lets MapLibre's `RasterSource` consume them via the per-layer `tileUrlTemplate`.

See [`docs/architecture.md`](docs/architecture.md) and the ADRs under [`docs/adr/`](docs/adr/) for the why behind each piece.

## Repository layout

```
schema/     # JSON Schema for the manifest contract (v2) — single source of truth
backend/    # Python ingest + FastAPI tile server + Caddy + systemd (Hetzner VPS)
  src/radar/      module: meteofrance, grib, radar_hdf5, tiles, tile_server, ...
  systemd/        radar-{ingest,nowcast,cleanup}.timer, arome-ingest.timer,
                  radar-tileserver.service
  caddy/          Caddyfile (prod, HTTPS) + Caddyfile.dev (HTTP)
  deploy/         install.sh + update.sh + env.example
client/     # Kotlin Multiplatform app (Compose Multiplatform for UI)
docs/       # Architecture + 4 ADRs (incl. ADR-0004 on the lazy tile server)
dev/        # Local-dev tooling (fake-data.py is currently v1-stale; see CLAUDE.md)
tools/      # Misc CI helpers
```

## Local quick start

```bash
# 1. One-off bootstrap (installs uv and the Gradle wrapper jar)
./setup.sh

# 2. Backend tests + lint
make backend-test
make backend-lint

# 3. Schema + example consistency
make schema-validate
```

For an end-to-end demo against the live backend, point your client at the VPS (see Production deployment) using HTTP basic-auth credentials.

> Note: the local-dev `make dev-stack` path relies on `dev/fake-data.py`, which was written for the v1 (pre-render) manifest and is currently incompatible with v2. Updating it is a backlog item — for now, develop against the real VPS.

## Production deployment

The backend is designed for a single Debian 12+ Hetzner VPS (cheap tier — CX22 / CAX11). Full procedure:

```bash
ssh root@your-vps
git clone https://github.com/<you>/french-rain-radar /opt/radar
cd /opt/radar/backend/deploy
./install.sh           # apt deps, uv, radar user, systemd units (incl. tileserver),
                       # Caddy + caddy-ratelimit module, dirs, env.example -> /etc/radar/env

# Then edit:
nano /etc/radar/env             # METEOFRANCE_TOKEN_AROME, METEOFRANCE_TOKEN_RADAR, bbox
caddy hash-password             # for each basic-auth user
nano /etc/caddy/Caddyfile       # replace hostname + bcrypt hash placeholders
systemctl reload caddy

sudo -u radar bash -c 'set -a; source /etc/radar/env; set +a; /opt/radar/backend/.venv/bin/radar init-manifest'
```

After that the systemd timers do the rest: radar ingest every 5 min, AROME ingest hourly at HH:10, cleanup daily.

See [`docs/deployment.md`](docs/deployment.md) for full detail, [`backend/deploy/README.md`](backend/deploy/README.md) for the Caddy + xcaddy specifics, and [`docs/data-sources.md`](docs/data-sources.md) for everything we learned about the Météo-France APIs.

## Auto-deploy

GitHub Actions auto-deploys backend changes on push to `main` after CI passes. See [`.github/workflows/deploy-backend.yml`](.github/workflows/deploy-backend.yml). Three secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, plus an environment named `production`. The deploy SSHs into the VPS as a dedicated `deploy` user that has `sudo NOPASSWD` for `/opt/radar/backend/deploy/update.sh` only.

## Licence

TBD — pick one before publishing. AGPL-3.0 is a reasonable default for self-hosted services. The Météo-France data itself is under the **Licence Ouverte / Etalab**; clients must credit "Source: Météo-France".
