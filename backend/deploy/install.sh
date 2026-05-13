#!/usr/bin/env bash
# Bootstrap a fresh Debian 12+ VPS to host the radar pipeline. Idempotent.
# Run as root.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/radar}"

if [ "$EUID" -ne 0 ]; then
    echo "must run as root" >&2
    exit 1
fi

echo "[1/8] apt deps..."
apt update
DEBIAN_FRONTEND=noninteractive apt install -y \
    python3.12 python3.12-venv libeccodes-dev \
    curl ca-certificates gnupg

echo "[2/8] uv..."
# Install uv system-wide so the unprivileged `radar` user can find it.
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi
# Handle the case where a previous run installed uv into /root/.local/bin/:
if [ -x /root/.local/bin/uv ] && [ ! -x /usr/local/bin/uv ]; then
    install -m 0755 /root/.local/bin/uv  /usr/local/bin/uv
    install -m 0755 /root/.local/bin/uvx /usr/local/bin/uvx
fi
command -v uv >/dev/null 2>&1 || { echo "uv install failed" >&2; exit 1; }

echo "[3/8] user + paths..."
id -u radar >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin radar
install -d -o radar -g radar /var/lib/radar/tiles /var/log/caddy
install -d /etc/radar

echo "[4/8] backend deps..."
chown -R radar:radar "$REPO_ROOT"
sudo -u radar bash -lc "cd $REPO_ROOT/backend && uv sync"

echo "[5/8] env file..."
if [ ! -f /etc/radar/env ]; then
    cp "$REPO_ROOT/backend/deploy/env.example" /etc/radar/env
    chmod 640 /etc/radar/env
    chown root:radar /etc/radar/env
    echo "  -> created /etc/radar/env (edit and fill in METEOFRANCE_TOKEN)"
fi

echo "[6/8] systemd units..."
install -m 644 "$REPO_ROOT/backend/systemd/"*.service /etc/systemd/system/
install -m 644 "$REPO_ROOT/backend/systemd/"*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now radar-ingest.timer radar-nowcast.timer arome-ingest.timer radar-cleanup.timer

echo "[7/8] Caddy with rate-limit module..."
if ! command -v caddy >/dev/null 2>&1; then
    apt install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt update
    apt install -y caddy
fi

# Add the rate_limit module in place. Works on Caddy >= 2.7 installed from
# the official deb package. Replaces /usr/bin/caddy with a build that includes
# the extra plugin. Will try to reload Caddy and fail because the Caddyfile
# still has placeholders -- that's expected; we install the file next.
caddy add-package github.com/mholt/caddy-ratelimit || true

install -m 644 "$REPO_ROOT/backend/caddy/Caddyfile" /etc/caddy/Caddyfile

echo "[8/8] done."
cat <<'POST'

Next steps (manual, one-time):
  1. Edit /etc/radar/env and fill in METEOFRANCE_TOKEN.
  2. Edit /etc/caddy/Caddyfile and replace the three placeholders:
        - hostname  (radar.yourdomain.tld)
        - email     (you@example.com, or delete the {email ...} block)
        - bcrypt hash for each user  (generate with: caddy hash-password)
  3. caddy validate --config /etc/caddy/Caddyfile
  4. systemctl restart caddy && systemctl status caddy --no-pager
  5. sudo -u radar /opt/radar/backend/.venv/bin/radar init-manifest
POST
