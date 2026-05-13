# Deployment

Target: a single Debian 12+ Hetzner VPS (cheap tier, CX22 / CAX11, 2 vCPU / 4 GB).

## One-time bootstrap

```bash
ssh root@your-vps
git clone https://github.com/<you>/french-rain-radar /opt/radar
cd /opt/radar/backend/deploy
./install.sh
```

`install.sh` (idempotent) does:

1. Installs apt deps: `python3.12`, `python3.12-venv`, `libeccodes-dev`.
2. Installs **`uv`** system-wide at `/usr/local/bin/uv` (so the unprivileged `radar` user can find it).
3. Creates the `radar` system user and the directory layout under `/var/lib/radar/tiles/{sources,cache}/`.
4. Runs `uv sync` as the `radar` user against `/opt/radar/backend/pyproject.toml`.
5. Copies `env.example` → `/etc/radar/env` if it doesn't already exist (so a re-run won't clobber your secrets).
6. Installs the systemd units (4 timers + 1 service) and enables them:
   - `radar-ingest.timer` (5-min radar mosaic download)
   - `radar-nowcast.timer` (5-min, pysteps — currently placeholder)
   - `arome-ingest.timer` (hourly AROME-PI run download)
   - `radar-cleanup.timer` (daily retention)
   - **`radar-tileserver.service`** (long-lived FastAPI tile renderer on `127.0.0.1:8765`)
7. Installs Caddy from Cloudsmith + adds the `caddy-ratelimit` module via `caddy add-package`.
8. Installs the Caddyfile placeholder to `/etc/caddy/Caddyfile`.

After `install.sh`, three things still need manual editing:

```bash
nano /etc/radar/env              # METEOFRANCE_TOKEN_AROME, METEOFRANCE_TOKEN_RADAR
caddy hash-password              # for each user
nano /etc/caddy/Caddyfile        # replace hostname + bcrypt hash placeholders

caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
systemctl restart radar-tileserver

sudo -u radar bash -c 'set -a; source /etc/radar/env; set +a; /opt/radar/backend/.venv/bin/radar init-manifest'
```

## DNS + TLS

Point `radar.yourdomain.tld` at the VPS. The Caddyfile's site block is the bare hostname (or `:80` for HTTP-only testing). Caddy fetches a Let's Encrypt cert automatically on first request to the hostname.

## Adding a user

```bash
caddy hash-password
# paste the hash into /etc/caddy/Caddyfile under `basic_auth`
systemctl reload caddy
```

## Updating

Automatic on push to `main` once `backend` CI passes — `deploy-backend.yml` SSHs in and runs `update.sh`. Manual:

```bash
ssh root@your-vps
sudo /opt/radar/backend/deploy/update.sh
```

`update.sh` does:
- `git pull --ff-only` as `radar`
- `uv sync` to pick up new deps
- Re-installs systemd unit files in case they changed
- Restarts the 4 timers and the long-lived `radar-tileserver.service`
- **Does not** touch `/etc/radar/env` or `/etc/caddy/Caddyfile` (secrets / user passwords stay)

## Operational tools

- **All recent journal output:** `journalctl -u 'radar-*' -u 'arome-*' --since '30 min ago'`
- **Tile-server logs:** `journalctl -u radar-tileserver -f`
- **Manual radar ingest:** `sudo -u radar bash -c 'set -a; source /etc/radar/env; set +a; /opt/radar/backend/.venv/bin/radar ingest-radar'`
- **Manual AROME ingest:** same pattern with `ingest-arome` (idempotent, top-ups partial runs)
- **Timer status:** `systemctl list-timers 'radar-*' 'arome-*'`
- **Disk usage:** `du -sh /var/lib/radar/tiles/{sources,cache}`
- **Trigger a deploy from your laptop:** `gh workflow run deploy-backend.yml`

## Inspect the live data

```bash
# Manifest summary (auth required)
curl -u user:pw https://radar.yourdomain.tld/manifest.json | jq '.layers | to_entries[] | {key, frames: .value.frames|length, runTime: .value.runTime}'

# Force-render a specific tile and time it (cold = render, warm = cache hit)
time curl -u user:pw -o /tmp/t.png https://radar.yourdomain.tld/radar/<ts>/<z>/<x>/<y>.png
```

## Backups

The pipeline is fully reproducible from Météo-France — no data backup needed. Worth backing up:

- `/etc/caddy/Caddyfile` (basic-auth bcrypt hashes)
- `/etc/radar/env` (Météo-France API tokens)
- `/home/deploy/.ssh/` (the GitHub Actions deploy key)
