# Deployment

Target: a single Debian 12+ Hetzner VPS (cheap tier, e.g. CX22 or CAX11, 2 vCPU / 4 GB).

## One-time bootstrap on the VPS

```bash
ssh root@your-vps
git clone https://github.com/<you>/french-rain-radar /opt/radar
cd /opt/radar/backend/deploy
./install.sh
```

`install.sh`:

- installs Python 3.12, `libeccodes-dev`, `uv`, Caddy (with the `caddy-ratelimit` module);
- creates an unprivileged `radar` user;
- installs the systemd `.service` + `.timer` units from `backend/systemd/`;
- installs `backend/caddy/Caddyfile` to `/etc/caddy/Caddyfile`;
- copies `env.example` to `/etc/radar/env` (which you then edit to fill in the Météo-France token and the bounding box).

## DNS + TLS

Point `radar.yourdomain.tld` at the VPS, then `systemctl reload caddy`. Caddy fetches a Let's Encrypt certificate automatically on first request.

## Adding a user

```bash
caddy hash-password
# paste the hash into /etc/caddy/Caddyfile under `basic_auth`
systemctl reload caddy
```

## Update procedure

```bash
cd /opt/radar
sudo -u radar git pull
sudo /opt/radar/backend/deploy/update.sh
```

`update.sh` runs `uv sync` and restarts the timers so a long-lived pipeline picks up new code on the next firing.

## Operational tools

- **Logs:** `journalctl -u radar-ingest.timer --since '1 hour ago'`
- **Manual run:** `sudo -u radar /opt/radar/backend/.venv/bin/radar ingest-radar`
- **Status:** `systemctl list-timers radar-*`
- **Disk usage:** `du -sh /var/lib/radar/tiles`
- **Caddy logs:** `tail -F /var/log/caddy/radar.log`

## Backups

The pipeline is fully reproducible from Météo-France — no backup needed except `/etc/caddy/Caddyfile` (passwords) and `/etc/radar/env` (API token).
