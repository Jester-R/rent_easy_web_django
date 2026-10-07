# RentEasy dev - minimal cross-platform commands (Linux/macOS + Windows).
#   just setup     build everything: uv/pip venv + bolt patch + JS deps
#   just backend   start only the backend (runbolt on PORT)
#   just frontend  start only the Angular app (ng serve; bun, else node/npm)
#   just run       start both together (Ctrl+C stops them)
#
# Each recipe is defined once for Unix and once for Windows ([unix]/[windows]);
# just picks the matching variant automatically.

set dotenv-load := true

port := "8123"

# Create backend venv + install deps (venv/sync via uv when present), patch django-bolt, install frontend deps
[unix]
setup:
    @cd backend && { [ -d .venv ] || { command -v uv >/dev/null 2>&1 && uv venv || { python3 -m venv .venv || python -m venv .venv; }; }; }
    @cd backend && { command -v uv >/dev/null 2>&1 && uv sync || { .venv/bin/python -m pip install --upgrade pip >/dev/null && .venv/bin/python -m pip install "django==6.1.1" "django-bolt>=0.11.1" "sqlparse==0.6.0" "whitenoise==6.12.0"; }; }
    @cd backend && .venv/bin/python tools/patch_bolt.py
    @cd frontend && { command -v bun >/dev/null 2>&1 && bun install || { command -v npm >/dev/null 2>&1 && npm install || echo "frontend deps skipped: install bun or node/npm"; }; }

[windows]
setup:
    @cd /d backend && if exist ".venv" (echo venv already present) else ((where uv >nul 2>nul && uv venv) || (py -3 -m venv .venv || python -m venv .venv))
    @cd /d backend && (where uv >nul 2>nul && uv sync) || (.venv\Scripts\python.exe -m pip install --upgrade pip && .venv\Scripts\python.exe -m pip install "django==6.1.1" "django-bolt>=0.11.1" "sqlparse==0.6.0" "whitenoise==6.12.0")
    @cd /d backend && .venv\Scripts\python.exe tools/patch_bolt.py
    @cd /d frontend && (where bun >nul 2>nul && bun install) || ((where npm >nul 2>nul && npm install) || echo frontend deps skipped: install bun or node/npm)

# Start only the backend (runbolt on PORT)
[unix]
backend:
    @cd backend && { command -v nix >/dev/null 2>&1 && nix develop --command .venv/bin/python manage.py runbolt --host 127.0.0.1 --port {{port}} --no-admin || .venv/bin/python manage.py runbolt --host 127.0.0.1 --port {{port}} --no-admin; }

[windows]
backend:
    @cd /d backend && .venv\Scripts\python.exe manage.py runbolt --host 127.0.0.1 --port {{port}} --no-admin

# Start only the Angular frontend (ng serve on :4200; bun, else node/npm)
[unix]
frontend:
    @cd frontend && { command -v bun >/dev/null 2>&1 && bunx ng serve || { command -v npm >/dev/null 2>&1 && npm start || echo "frontend needs bun or node/npm"; }; }

[windows]
frontend:
    @cd /d frontend && (where bun >nul 2>nul && bunx ng serve) || ((where npm >nul 2>nul && npm start) || echo frontend needs bun or node/npm)

# Build the Angular frontend for production (bun, else node/npm)
[unix]
build:
    @cd frontend && { command -v bun >/dev/null 2>&1 && bun run build || { command -v npm >/dev/null 2>&1 && npm run build || echo "frontend build needs bun or node/npm"; }; }

[windows]
build:
    @cd /d frontend && (where bun >nul 2>nul && bun run build) || ((where npm >nul 2>nul && npm run build) || echo frontend build needs bun or node/npm)

# Start both: backend in the background, frontend in the foreground
[unix]
run:
    @{{just_executable()}} backend > /tmp/bolt.log 2>&1 &
    @{{just_executable()}} frontend

# Start both: backend in its own window, frontend in the foreground
[windows]
run:
    @start "renteasy-backend" {{just_executable()}} backend
    @{{just_executable()}} frontend