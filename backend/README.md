# backend/

Python pipeline that fetches Météo-France data, generates PNG tiles + a `manifest.json`, and exposes them through Caddy.

## Layout

```
src/radar/        Python package (entry point: `radar` CLI)
tests/            pytest suite
systemd/          .service + .timer units installed on the VPS
caddy/            Caddyfile (prod + dev)
deploy/           install/update scripts for the Hetzner VPS
```

## Local dev

```bash
uv sync           # install deps
uv run radar --help
uv run pytest
uv run ruff check .
```

## CLI subcommands

| Command | What it does | Cadence in prod |
|---|---|---|
| `radar ingest-radar` | Fetch the latest radar mosaic, render PNG, update manifest. | every 5 min |
| `radar nowcast`      | Run pysteps on the latest radar frames, render nowcast PNGs. | every 5 min |
| `radar ingest-arome` | Fetch AROME-NWC, render forecast PNGs. | hourly |
| `radar cleanup`      | Delete PNGs older than the retention window. | daily |

Each is invoked by a matching systemd timer (see `systemd/`).

## Configuration

Read via `pydantic-settings` from environment variables — usually loaded by systemd from `/etc/radar/env`. See `deploy/env.example`.

## State of the code

Right now the modules are scaffolds. Each function has the right signature and docstring but is unimplemented — `phase 0` work is to fill them in starting with `meteofrance.py` and `grib.py`.
