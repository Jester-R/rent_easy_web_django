#!/usr/bin/env bash
# Start RentEasy web in the foreground and share it over the internet with ngrok.
# Press CTRL+C to stop BOTH the server and the tunnel.
#
#   ./run.sh                 # local :8010 + public ngrok URL
#   PORT=9000 ./run.sh       # different port
#   ./run.sh --reset         # re-seed the demo data first
#   ./run.sh --no-ngrok      # local only
#   ./run.sh --ngrok-domain  # reserved domain from ~/.config/ngrok/ngrok.yml

set -uo pipefail

cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
RentEasy web - development server (+ ngrok public URL)

  ./run.sh                 # start on :8010 and expose it via ngrok
  PORT=9000 ./run.sh       # different port
  ./run.sh --reset         # re-seed the demo data first
  ./run.sh --no-ngrok      # local only, no public URL

Options:
  --reset           wipe app data and reload the demo dataset before starting
  --no-ngrok        do not start a tunnel
  -h, --help        show this help


The public URL is printed once the tunnel is up; share it and press CTRL+C
to shut everything down. While the tunnel is open anyone with the link can
reach the demo, admin account included - close it after your demo.
EOF
}

PORT="${PORT:-8010}"
PYTHON=".venv/bin/python"
RESET=0
USE_NGROK=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --reset) RESET=1 ;;
    --no-ngrok) USE_NGROK=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; echo "" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ ! -x "$PYTHON" ]; then
  echo "virtualenv missing: create .venv first (python3 -m venv .venv)" >&2
  exit 1
fi

command -v ngrok >/dev/null 2>&1 || USE_NGROK=0

# free the port if a previous run is still holding it
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
  sleep 1
fi

"$PYTHON" manage.py migrate --noinput || exit 1
if [ "$RESET" -eq 1 ]; then
  "$PYTHON" manage.py seed_demo --reset || exit 1
fi
"$PYTHON" manage.py collectstatic --noinput --clear >/dev/null || exit 1

NGROK_PID=""
SERVER_PID=""

stop_tunnel() {
  [ -n "$NGROK_PID" ] || return 0
  kill -0 "$NGROK_PID" 2>/dev/null || return 0
  echo ""
  echo "closing ngrok tunnel ..."
  kill "$NGROK_PID" 2>/dev/null
  wait "$NGROK_PID" 2>/dev/null
}

stop_all() {
  stop_tunnel
  echo "stopping RentEasy ..."
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  return 0
}

on_signal() {
  trap - INT TERM
  stop_all
  exit 130
}

# no EXIT trap on purpose: command substitution runs in subshells that would
# inherit it and print the shutdown banner while the server is still running
trap on_signal INT TERM

# ngrok prints "url=https://..." in its own log once the tunnel is live; reading
# it there (instead of the :4040 API) means we never pick up another agent's URL
tunnel_url() {
  local log=/tmp/opencode/ngrok.log
  for _ in $(seq 1 30); do
    kill -0 "$NGROK_PID" 2>/dev/null || return 1
    if grep -q "ERR_NGROK_" "$log" 2>/dev/null; then
      return 2
    fi
    url=$(grep -oE 'url=https://[^ "]+' "$log" 2>/dev/null | head -1 | sed 's/^url=//')
    [ -n "$url" ] && { printf '%s' "$url"; return 0; }
    sleep 0.4
  done
  return 1
}

PUBLIC_URL=""

# the tunnel starts first so Django can trust its origin before it boots
if [ "$USE_NGROK" -eq 1 ]; then
  NGROK_CONFIG="$HOME/.config/ngrok/ngrok.yml"
  if ! grep -q "authtoken:" "$NGROK_CONFIG" 2>/dev/null; then
    echo "  ngrok has no authtoken - run: ngrok config add-authtoken <your token>"
    echo "  starting local only ..."
    echo ""
  else
    ngrok_args=(http "$PORT" --log=stdout --log-level=info)
    : >/tmp/opencode/ngrok.log
    ngrok "${ngrok_args[@]}" >/tmp/opencode/ngrok.log 2>&1 &
    NGROK_PID=$!
    tunnel_url
    status=$?
    if [ "$status" -eq 0 ]; then
      PUBLIC_URL=$(grep -oE 'url=https://[^ "]+' /tmp/opencode/ngrok.log | head -1 | sed 's/^url=//')
    else
      kill "$NGROK_PID" 2>/dev/null
      wait "$NGROK_PID" 2>/dev/null
      NGROK_PID=""
      PUBLIC_URL=""
      echo "  ngrok tunnel not started:"
      grep -oE 'msg="[^"]*"[^|]*' /tmp/opencode/ngrok.log | tail -1 | sed 's/^/    /'
      echo "    stop any other ./run.sh or ngrok that is still running,"
      echo "    or start local only with --no-ngrok"
      echo ""
    fi
    if [ -n "$PUBLIC_URL" ]; then
      # ngrok terminates TLS, so the browser posts https:// origins at an http://
      # Django. Trust the forwarding header and the tunnel origin (config/settings.py)
      export TRUST_FORWARDED_PROTO=1
      export EXTRA_CSRF_TRUSTED_ORIGINS="$PUBLIC_URL"
    fi
  fi
fi

"$PYTHON" manage.py runbolt --host 0.0.0.0 --port "${PORT}" &
SERVER_PID=$!

echo ""
echo "  RentEasy  ->  http://localhost:${PORT}/"
echo "  admin / admin   ·   owner / owner   ·   renter / renter"
echo "  press CTRL+C to stop"
if [ -n "$PUBLIC_URL" ]; then
  echo ""
  echo "  PUBLIC URL  ->  ${PUBLIC_URL}"
  echo "  share that link; it dies as soon as you press CTRL+C"
fi
echo ""

wait "$SERVER_PID"
stop_all
