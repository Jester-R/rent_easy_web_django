# Run `just` from the project root. Unix and Windows commands are kept separate
# because their virtual environment paths and shells differ.

set dotenv-load := true

port := "8123"

# Create the backend environment, install Python packages, and install frontend packages.
[unix]
setup:
    @cd backend && if command -v uv >/dev/null 2>&1; then uv sync; else python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -e .; fi
    @cd backend && .venv/bin/python manage.py migrate
    @cd backend && .venv/bin/python manage.py seed_demo
    @cd frontend && if command -v bun >/dev/null 2>&1; then bun install; else npm install; fi

[windows]
setup:
    @cd /d backend && (where uv >nul 2>nul && uv sync) || (py -3 -m venv .venv && .venv\Scripts\python.exe -m pip install --upgrade pip && .venv\Scripts\python.exe -m pip install -e .)
    @cd /d backend && .venv\Scripts\python.exe manage.py migrate
    @cd /d backend && .venv\Scripts\python.exe manage.py seed_demo
    @cd /d frontend && (where bun >nul 2>nul && bun install) || npm install

# Apply database migrations.
[unix]
migrate:
    @cd backend && .venv/bin/python manage.py migrate

[windows]
migrate:
    @cd /d backend && .venv\Scripts\python.exe manage.py migrate

# Create demo accounts and sample content. Use `just seed -- --reset` to recreate them.
[unix]
seed *ARGS:
    @cd backend && .venv/bin/python manage.py seed_demo {{ARGS}}

[windows]
seed *ARGS:
    @cd /d backend && .venv\Scripts\python.exe manage.py seed_demo {{ARGS}}

# Start the backend API.
[unix]
backend:
    @cd backend && .venv/bin/python manage.py runbolt --host 127.0.0.1 --port {{port}} --no-admin

[windows]
backend:
    @cd /d backend && .venv\Scripts\python.exe manage.py runbolt --host 127.0.0.1 --port {{port}} --no-admin

# Start the frontend development server.
[unix]
frontend:
    @cd frontend && if command -v bun >/dev/null 2>&1; then bunx ng serve; else npm start; fi

[windows]
frontend:
    @cd /d frontend && (where bun >nul 2>nul && bunx ng serve) || npm start

# Build the frontend.
[unix]
build:
    @cd frontend && if command -v bun >/dev/null 2>&1; then bun run build; else npm run build; fi

[windows]
build:
    @cd /d frontend && (where bun >nul 2>nul && bun run build) || npm run build

# Start backend in the background and frontend in the foreground.
[unix]
run:
    @{{just_executable()}} backend > /tmp/bolt.log 2>&1 &
    @{{just_executable()}} frontend

[windows]
run:
    @start "renteasy-backend" {{just_executable()}} backend
    @{{just_executable()}} frontend
