#!/usr/bin/env bash
# RentEasy Web - one-shot development launcher (Angular + Django Bolt).
#
#   ./run.sh                # set up if needed, then run backend + frontend
#   ./run.sh --reset        # re-seed the demo data before starting
#   ./run.sh --no-setup     # skip dependency/install checks, just run
#   ./run.sh --backend-only # start only Django Bolt on :8123
#   ./run.sh --frontend-only# start only Angular on :4200
#
# Press CTRL+C to stop everything.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8123}"
FRONTEND_PORT="${FRONTEND_PORT:-4200}"
LOG_DIR="${TMPDIR:-/tmp}/renteasy"
mkdir -p "$LOG_DIR"

RESET=0
SETUP=1
ONLY=""

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --reset) RESET=1 ;;
    --no-setup) SETUP=0 ;;
    --backend-only) ONLY="backend" ;;
    --frontend-only) ONLY="frontend" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# Common per-user tool locations for non-interactive shells.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# uv can install and manage the exact Python version the backend pins (.python-version).
ensure_uv() {
  have uv && return 0
  if have curl; then
    info "uv not found - installing it to ~/.local/bin ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif have wget; then
    info "uv not found - installing it to ~/.local/bin ..."
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    die "need uv, curl or wget to set up the Python environment"
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  have uv || die "uv installation failed; install it manually from https://astral.sh/uv"
}

setup_backend() {
  ensure_uv
  info "Syncing backend environment (this fetches Python 3.14 on first run)..."
  ( cd backend && uv sync )
}

setup_frontend() {
  if have bun; then
    info "Installing frontend dependencies (bun)..."
    ( cd frontend && bun install )
  elif have npm; then
    info "Installing frontend dependencies (npm)..."
    ( cd frontend && npm install )
  else
    die "need bun or npm to install the Angular frontend"
  fi
}

backend_pid=""
cleanup() {
  local code=$?
  trap - INT TERM EXIT
  if [ -n "$backend_pid" ] && kill -0 "$backend_pid" 2>/dev/null; then
    info "Stopping backend..."
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
  exit "$code"
}
trap cleanup INT TERM EXIT

wait_for_backend() {
  for _ in $(seq 1 120); do
    if (exec 3<>"/dev/tcp/127.0.0.1/${BACKEND_PORT}") 2>/dev/null; then
      exec 3>&- 2>/dev/null || true
      return 0
    fi
    kill -0 "$backend_pid" 2>/dev/null || return 1
    sleep 0.5
  done
  return 1
}

start_backend() {
  info "Starting Django Bolt on http://127.0.0.1:${BACKEND_PORT} (log: ${LOG_DIR}/backend.log)"
  ( cd backend && .venv/bin/python manage.py runbolt \
      --host 127.0.0.1 --port "$BACKEND_PORT" --no-admin ) \
      >"${LOG_DIR}/backend.log" 2>&1 &
  backend_pid=$!
}

start_frontend() {
  info "Starting Angular on http://localhost:${FRONTEND_PORT}"
  if have bun; then
    ( cd frontend && bunx ng serve --port "$FRONTEND_PORT" )
  else
    ( cd frontend && npm start -- --port "$FRONTEND_PORT" )
  fi
}

# --- dependency setup -------------------------------------------------------
if [ "$ONLY" != "frontend" ]; then
  if [ "$SETUP" -eq 1 ]; then
    [ -x backend/.venv/bin/python ] || setup_backend
  else
    [ -x backend/.venv/bin/python ] || die "backend env missing; drop --no-setup to install it"
  fi
fi

if [ "$ONLY" != "backend" ]; then
  if [ "$SETUP" -eq 1 ]; then
    [ -d frontend/node_modules ] || setup_frontend
  else
    [ -d frontend/node_modules ] || die "frontend deps missing; drop --no-setup to install them"
  fi
fi

# --- database ---------------------------------------------------------------
if [ "$ONLY" != "frontend" ]; then
  fresh_db=0
  [ -f backend/db.sqlite3 ] || fresh_db=1
  info "Applying database migrations..."
  ( cd backend && .venv/bin/python manage.py migrate --noinput )

  if [ "$RESET" -eq 1 ]; then
    info "Re-seeding demo data..."
    ( cd backend && .venv/bin/python manage.py seed_demo --reset )
  elif [ "$fresh_db" -eq 1 ]; then
    info "Seeding demo data..."
    ( cd backend && .venv/bin/python manage.py seed_demo )
  fi
fi

# --- run --------------------------------------------------------------------
if [ "$ONLY" = "backend" ]; then
  start_backend
  info "Backend ready. Press CTRL+C to stop."
  wait "$backend_pid"
elif [ "$ONLY" = "frontend" ]; then
  start_frontend
else
  echo ""
  echo "  Demo accounts:  admin/admin  ·  owner/owner  ·  renter/renter"
  echo ""
  start_backend
  if wait_for_backend; then
    info "Backend is up."
  else
    warn "backend did not become ready; check ${LOG_DIR}/backend.log"
  fi
  start_frontend
fi
