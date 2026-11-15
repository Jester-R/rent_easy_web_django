#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/renteasy}"
APP_USER="${APP_USER:-renteasy}"

command="set -a; . '$APP_DIR/.env'; set +a; cd '$APP_DIR/backend' && exec .venv/bin/python manage.py set_telegram_webhook --ensure"

if [ "$(id -u)" -eq 0 ]; then
  exec runuser -u "$APP_USER" -- bash -lc "$command"
fi

exec bash -lc "$command"
