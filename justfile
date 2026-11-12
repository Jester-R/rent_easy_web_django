# Run `just` from the project root. Unix and Windows commands are kept separate
# because their virtual environment paths and shells differ.

set dotenv-load := true

port := "8000"

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

# Register the Telegram bot webhook (uses FRONTEND_BASE_URL unless --url is given).
[unix]
telegram-webhook *ARGS:
    @cd backend && .venv/bin/python manage.py set_telegram_webhook {{ARGS}}

[windows]
telegram-webhook *ARGS:
    @cd /d backend && .venv\Scripts\python.exe manage.py set_telegram_webhook {{ARGS}}

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
    @cd frontend && export __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS="${__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS:-$ALLOWED_HOSTS}"; if command -v bun >/dev/null 2>&1; then bunx ng serve; else npm start; fi

[windows]
frontend:
    @cd /d frontend && (set "__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=%ALLOWED_HOSTS%" & ((where bun >nul 2>nul && bunx ng serve) || npm start))

# Build the frontend and emit index.html for static hosting.
[unix]
build-frontend:
    @cd frontend && if command -v bun >/dev/null 2>&1; then bun run build; else npm run build; fi

[windows]
build-frontend:
    @cd /d frontend && (where bun >nul 2>nul && bun run build) || npm run build

# Start backend in the background and frontend in the foreground.
[unix]
run:
    @{{just_executable()}} telegram-webhook || true
    @{{just_executable()}} backend > /tmp/bolt.log 2>&1 &
    @{{just_executable()}} frontend

[windows]
run:
    @start "renteasy-backend" {{just_executable()}} backend
    @{{just_executable()}} frontend


# Set up dependencies, build frontend, and prepare tarballs in package/.
[unix]
pack:
    @{{just_executable()}} setup
    @{{just_executable()}} build-frontend
    rm -rf package
    mkdir -p package
    @if [ -f .env ]; then cp .env backend/.env; fi
    tar -czf package/backend.tar.gz -C backend \
        --exclude='*/__pycache__' \
        --exclude='*.pyc' \
        --exclude='*/db.sqlite3*' \
        --exclude='*/media' \
        --exclude='*/staticfiles' \
        .
    @if [ -f .env ]; then rm -f backend/.env; fi
    tar -czf package/frontend.tar.gz -C frontend/dist/frontend .

    echo "Created package/backend.tar.gz and package/frontend.tar.gz"

[windows]
pack:
    @{{just_executable()}} setup
    @{{just_executable()}} build-frontend
    @if exist package rmdir /s /q package
    @mkdir package
    @if exist .env copy /y .env backend\.env >nul
    @tar -czf package\backend.tar.gz -C backend --exclude=__pycache__ --exclude=*/__pycache__ --exclude=*.pyc --exclude=db.sqlite3* --exclude=*/db.sqlite3* --exclude=media --exclude=*/media --exclude=staticfiles --exclude=*/staticfiles .
    @if exist .env del /q backend\.env
    @tar -czf package\frontend.tar.gz -C frontend/dist/frontend .
    @echo Created package\backend.tar.gz and package\frontend.tar.gz

# Copy the prepared backend and frontend tarballs to a destination path (prompts when omitted).
[unix]
deploy dest="":
    #!/usr/bin/env bash
    set -euo pipefail

    for archive in package/backend.tar.gz package/frontend.tar.gz; do
        if [[ ! -f "$archive" ]]; then
            echo "$archive not found; run 'just pack' first" >&2
            exit 1
        fi
    done

    destination={{quote(dest)}}
    if [[ -z "$destination" ]]; then
        read -r -p "Deploy destination path: " destination
    fi
    if [[ -z "$destination" ]]; then
        echo "destination path is required" >&2
        exit 1
    fi

    if [[ "$destination" == *:* ]]; then
        scp package/backend.tar.gz package/frontend.tar.gz "$destination"/
    else
        mkdir -p "$destination"
        cp package/backend.tar.gz package/frontend.tar.gz "$destination"/
    fi

    echo "Deployed package/backend.tar.gz and package/frontend.tar.gz to $destination"

[windows]
[script("powershell.exe", "-NoProfile", "-File")]
deploy dest="":
    $ErrorActionPreference = "Stop"

    foreach ($archive in @("package/backend.tar.gz", "package/frontend.tar.gz")) {
        if (-not (Test-Path $archive)) {
            Write-Error "$archive not found; run 'just pack' first"
            exit 1
        }
    }

    $destination = {{quote(dest)}}
    if ([string]::IsNullOrWhiteSpace($destination)) {
        $destination = Read-Host "Deploy destination path"
    }
    if ([string]::IsNullOrWhiteSpace($destination)) {
        Write-Error "destination path is required"
        exit 1
    }

    if ($destination.Contains(":") -and $destination -notmatch "^[A-Za-z]:[\\/]") {
        scp package/backend.tar.gz package/frontend.tar.gz "${destination}/"
    } else {
        New-Item -ItemType Directory -Force -Path $destination | Out-Null
        Copy-Item package/backend.tar.gz, package/frontend.tar.gz -Destination $destination
    }

    Write-Host "Deployed package/backend.tar.gz and package/frontend.tar.gz to $destination"
