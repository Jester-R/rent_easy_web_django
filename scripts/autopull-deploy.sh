#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/renteasy}"
APP_USER="${APP_USER:-renteasy}"
BRANCH="${BRANCH:-main}"
SERVICE="${SERVICE:-renteasy-backend.service}"

exec 9>/run/renteasy-autopull.lock
flock -n 9 || exit 0

log() {
  printf '[autopull] %s\n' "$*"
}

run_as_app() {
  runuser -u "$APP_USER" -- "$@"
}

app_shell() {
  run_as_app bash -lc "$1"
}

APP_DIR=$(cd "$APP_DIR" && pwd)

before=$(run_as_app git -C "$APP_DIR" rev-parse HEAD)
run_as_app git -C "$APP_DIR" fetch --quiet origin "$BRANCH"
remote=$(run_as_app git -C "$APP_DIR" rev-parse "origin/$BRANCH")

if [ "$before" = "$remote" ]; then
  exit 0
fi

dirty=$(run_as_app git -C "$APP_DIR" status --porcelain --untracked-files=no)
if [ -n "$dirty" ]; then
  log "tracked files are modified; refusing to pull"
  printf '%s\n' "$dirty"
  exit 1
fi

log "updating ${before:0:7} -> ${remote:0:7}"
run_as_app git -C "$APP_DIR" pull --ff-only origin "$BRANCH"

app_shell "cd '$APP_DIR/backend' && uv sync --frozen"
app_shell "set -a; . '$APP_DIR/.env'; set +a; cd '$APP_DIR/backend' && .venv/bin/python manage.py migrate --noinput"
app_shell "cd '$APP_DIR/frontend' && npm install --legacy-peer-deps && npm run build"

index_csr="$APP_DIR/frontend/dist/frontend/browser/index.csr.html"
if [ -f "$index_csr" ]; then
  run_as_app cp "$index_csr" "$APP_DIR/frontend/dist/frontend/browser/index.html"
fi

if [ -f "$APP_DIR/scripts/autopull-deploy.sh" ]; then
  install -m 0755 "$APP_DIR/scripts/autopull-deploy.sh" /usr/local/bin/renteasy-autopull
fi

if [ -f "$APP_DIR/scripts/telegram-webhook-check.sh" ]; then
  install -m 0755 "$APP_DIR/scripts/telegram-webhook-check.sh" /usr/local/bin/renteasy-telegram-webhook
  install -m 0644 "$APP_DIR/scripts/renteasy-telegram-webhook.service" /etc/systemd/system/renteasy-telegram-webhook.service
  install -m 0644 "$APP_DIR/scripts/renteasy-telegram-webhook.timer" /etc/systemd/system/renteasy-telegram-webhook.timer
  systemctl daemon-reload
  systemctl enable --now renteasy-telegram-webhook.timer
fi

systemctl restart "$SERVICE"
log "deployed $(app_shell "git -C '$APP_DIR' rev-parse --short HEAD")"
