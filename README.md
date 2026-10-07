# RentEasy Web

RentEasy Web is a browser based rental platform built with an Angular frontend and an asynchronous Django backend powered by Django Bolt. It is the web companion to the RentEasy mobile app.

## Features

- **Renter portal:** browse and filter public property listings, save favorites, request bookings, and view payments.
- **Owner portal:** manage property listings, review booking requests, and track payments.
- **Superadmin console:** review platform activity and manage users, properties, bookings, and payments.
- **Public browsing:** visitors can explore listings without signing in. Sign in to use renter account features such as favorites and booking requests.
- **Language and theme preferences:** English and Khmer, with light and dark themes.
- **Notifications:** in-app notifications with unread counts.
- **Demo payment flows:** mock ABA Pay, Wing, and card payments, with refund support.

## Stack

- **Backend:** Python 3.14+, Django 6.1, Django Bolt, SQLite (WAL mode), and WhiteNoise.
- **Frontend:** Angular 22, TypeScript, Tailwind CSS 4, and RxJS.
- **Development tools:** `uv` for Python dependencies, Bun for JavaScript dependencies, and `just` for project commands.
- **Nix development shell:** provides Python, `uv`, Bun, `just`, and Ruff.

## Quick start

### With Nix (recommended)

From the repository root, enter the development shell, install dependencies, and start both apps:

```bash
nix develop
just setup
just run
```

Open [http://localhost:4200](http://localhost:4200). Angular runs on port `4200` and proxies API requests to Django Bolt on port `8123`. `just run` starts the backend and frontend; press `Ctrl+C` to stop the frontend, and stop the backend process if it remains running.

### Without Nix

Install Python 3.14+, `uv`, Bun, and [`just`](https://just.systems/), then run the same commands:

```bash
just setup
just run
```

`just setup` creates/synchronizes the backend virtual environment, applies the Django Bolt compatibility patch, and installs frontend packages. It uses `uv` and Bun when available, with pip and npm fallbacks.

## First run and demo data

After setup, initialize the database and seed the demo accounts and sample content:

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
cd ..
```

Then start the apps with `just run` from the repository root. To recreate the demo dataset, run:

```bash
cd backend
.venv/bin/python manage.py seed_demo --reset
```

The demo credentials are:

| Role | Username | Password | Portal |
| --- | --- | --- | --- |
| Superadmin | `admin` | `admin` | `/console` |
| Owner | `owner` | `owner` | `/owner` |
| Renter | `renter` | `renter` | `/renter` |

These are development accounts; change or remove them before deploying the application.

## Useful commands

Run these at the repository root:

| Command | Description |
| --- | --- |
| `just setup` | Set up Python and frontend dependencies. |
| `just run` | Start the backend and Angular development server. |
| `just backend` | Start only Django Bolt on `127.0.0.1:8123`. |
| `just frontend` | Start only Angular on `localhost:4200`. |
| `just build` | Build the Angular frontend for production. |

To run the services separately, use two terminals and run `just backend` in one and `just frontend` in the other.

## Project layout

```text
backend/    Django project, Django Bolt APIs, models, migrations, and seed command
frontend/   Angular application, routes, components, and API services
flake.nix   Nix development shell
justfile   Cross-platform development commands
```

## Notes

- The backend database is SQLite at `backend/db.sqlite3`.
- Django's traditional URL configuration remains for framework routes such as the admin; application JSON APIs are handled by Django Bolt.
- `backend/run.sh` is a legacy Django-only launcher for port `8010` and optional ngrok. For the current Angular + Django development workflow, use `just setup` and `just run`.
