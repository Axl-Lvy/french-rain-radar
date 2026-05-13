#!/usr/bin/env bash
# Pull latest code, re-sync deps, reload timers.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/radar}"

if [ "$EUID" -ne 0 ]; then
    echo "must run as root" >&2
    exit 1
fi

sudo -u radar bash -lc "cd $REPO_ROOT && git pull --ff-only"
sudo -u radar bash -lc "cd $REPO_ROOT/backend && uv sync"

# Re-install systemd units in case they changed.
install -m 644 "$REPO_ROOT/backend/systemd/"*.service /etc/systemd/system/
install -m 644 "$REPO_ROOT/backend/systemd/"*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl restart radar-ingest.timer radar-nowcast.timer arome-ingest.timer radar-cleanup.timer

# Re-install Caddyfile (does not touch passwords if you've edited them in /etc/caddy/Caddyfile directly).
# Comment this out if you maintain Caddyfile separately.
# install -m 644 "$REPO_ROOT/backend/caddy/Caddyfile" /etc/caddy/Caddyfile
# systemctl reload caddy

echo "update complete."
