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
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

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

echo "  NOTE: the rate_limit directive requires a custom Caddy build."
echo "        Easiest path:  apt install caddy && go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest"
echo "        Then:          xcaddy build --with github.com/mholt/caddy-ratelimit \\"
echo "                       --output /usr/bin/caddy"
echo "        Or use the docker image  caddy:builder-alpine  to produce the binary."

install -m 644 "$REPO_ROOT/backend/caddy/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "[8/8] done."
echo "       Edit /etc/radar/env, then:    systemctl start radar-ingest.service"
