# Deployment scripts

## Files

| File | Purpose |
|---|---|
| `install.sh` | One-time bootstrap on a fresh Debian 12+ VPS. Idempotent. Run as root. |
| `update.sh`  | Pull latest code, `uv sync`, restart timers. Run as root. |
| `env.example`| Copied to `/etc/radar/env` by `install.sh`. Edit before first run. |

## Caddy with the rate-limit module

The `rate_limit` directive used in `backend/caddy/Caddyfile` is **not** in the stock Caddy build. You have two options:

1. **`xcaddy`** (recommended on Debian):
   ```bash
   apt install -y golang-go
   go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
   xcaddy build --with github.com/mholt/caddy-ratelimit --output /usr/bin/caddy
   systemctl restart caddy
   ```
2. **Docker** if you don't want Go on the host:
   ```bash
   docker run --rm -v "$PWD":/out caddy:builder-alpine \
       sh -c 'xcaddy build --with github.com/mholt/caddy-ratelimit --output /out/caddy'
   install -m 0755 ./caddy /usr/bin/caddy
   systemctl restart caddy
   ```

## DNS + first run

1. Point `radar.yourdomain.tld` at the VPS public IP.
2. Edit `/etc/caddy/Caddyfile` — replace the placeholder bcrypt hash and the hostname.
3. `caddy hash-password` to generate hashes for each user.
4. `systemctl reload caddy` → ACME fetches the Let's Encrypt cert on first request.
5. Fill in `/etc/radar/env` (Météo-France token at minimum), then `systemctl start radar-ingest.service` to verify the pipeline.
