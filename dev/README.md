# dev/ — local development

This directory lets you run a realistic-looking version of the system on your
own machine, without a Hetzner VPS and without Météo-France credentials.

## Quick start

```bash
# 1. Bootstrap once
./setup.sh        # from repo root

# 2. Generate fake PNG tiles + a valid manifest into dev/data/tiles/
make fake-data

# 3. Start a local Caddy on http://localhost:8080 serving those tiles
make dev-caddy

# 4. Verify
curl -u dev:dev http://localhost:8080/manifest.json | jq .
curl -u dev:dev http://localhost:8080/radar/<timestamp>.png -o /tmp/frame.png
```

To take the local stack back down: `make dev-caddy-stop`.

## Files

- `docker-compose.yml` — runs Caddy (HTTP, port 8080) with `../backend/caddy/Caddyfile.dev`, serving `data/tiles/`.
- `fake-data.py` — generates a synthetic 24-frame radar history, 12-frame nowcast, and 6-frame forecast for the Apt/Avignon bbox, with shifting blobs of "rain" so the animation looks alive.

## Talking to the local stack from the client

| Target | Use this base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8080` |
| iOS simulator    | `http://localhost:8080` |
| Wasm (browser)   | `http://localhost:8080` |
| Physical device  | your host LAN IP (e.g. `http://192.168.1.42:8080`) |

Credentials: `dev` / `dev`.

## When you need real data

Once you have a Météo-France token, set `METEOFRANCE_TOKEN` in your shell and
run `cd backend && uv run radar ingest-radar` directly — it will write into
`dev/data/tiles/` (or wherever you've pointed `RADAR_TILE_DIR`).
