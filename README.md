# RentEasy Web

RentEasy Web is a browser based rental platform built with an Angular frontend and an asynchronous Django backend powered by Django Bolt. It is the web companion to the RentEasy mobile app.

## Features

- **Renter portal:** browse and filter public property listings, save favorites, request bookings, and view payments.
- **Owner portal:** manage property listings, review booking requests, and track payments.
- **Superadmin console:** review platform activity and manage users, properties, bookings, and payments.
- **Public browsing:** visitors can explore listings without signing in. Sign in to use renter account features such as favorites and booking requests.
- **Language and theme preferences:** English and Khmer, with light and dark themes.
- **Notifications:** in-app notifications with unread counts.
- **Payments:** real ABA PayWay hosted checkout (sandbox or production), with automatic mock fallback, plus demo Wing/card flows and refunds.
- **Rent hold and owner payouts:** rent is held by the platform for 7 days, cancellations/refunds are allowed during the hold, and admins record manual transfers to owner payout accounts.

## Stack

- **Backend:** Python 3.14+, Django 6.1, Django Bolt, and SQLite (WAL mode) — API only.
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

`just setup` creates/synchronizes the backend virtual environment, applies the Django Bolt compatibility patch, runs database migrations, and installs frontend packages. It uses `uv` and Bun when available, with pip and npm fallbacks.

## First run and demo data

After setup, seed the demo accounts and sample content:

```bash
cd backend
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

## Payments (ABA PayWay)

ABA payments use PayWay's **Ecommerce Checkout** hosted page. The backend creates a
`Pending` payment, signs the purchase fields, and the browser POSTs them to PayWay.
PayWay then either calls the backend callback or redirects the browser back to
`/payments/aba/return/`, where RentEasy asks PayWay for the authoritative status
(`check-transaction-2`) before showing the receipt. The payment detail page also
polls the refresh endpoint while a transaction is pending.

### Configuration

Copy `.env.example` to `.env` in the repository root and fill in the values.
`just` and `run.sh` load that file automatically; if you run Django or Angular
directly, export the same variables first.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ABA_PAYWAY_MERCHANT_ID` | empty | Sandbox or production merchant ID. |
| `ABA_PAYWAY_API_KEY` | empty | API key used to sign purchase, check, and callback payloads. |
| `ABA_PAYWAY_ENABLED` | `true` when both credentials are set | Set to `false` to force the mock gateway. |
| `ABA_PAYWAY_BASE_URL` | `https://checkout-sandbox.payway.com.kh` | Use `https://checkout.payway.com.kh` in production. |
| `ABA_PAYWAY_PAYMENT_OPTION` | empty | Empty shows all methods on the merchant profile; e.g. `cards` or `abapay_khqr`. |
| `ABA_PAYWAY_CURRENCY` | `USD` | `USD` or `KHR`. |
| `ABA_PAYWAY_LIFETIME_MINUTES` | `30` | Hosted checkout lifetime (PayWay minimum is 3). |
| `ABA_PAYWAY_TIMEOUT_SECONDS` | `15` | Timeout for backend PayWay API calls. |
| `RENT_HOLD_DAYS` | `7` | Days the platform holds rent before the owner payout is due. |
| `FRONTEND_BASE_URL` | `http://localhost:4200` | Used for return/cancel redirects into Angular. |
| `BACKEND_PUBLIC_URL` | `http://127.0.0.1:8123` | Public backend origin used to build the callback and return URLs. |
| `ABA_PAYWAY_CALLBACK_URL` | `{BACKEND_PUBLIC_URL}/payments/aba/callback/` | Server-to-server notification URL. |
| `ABA_PAYWAY_RETURN_URL` | `{BACKEND_PUBLIC_URL}/payments/aba/return/?payment={payment_id}` | Browser return URL after checkout. Keep the `{payment_id}` placeholder. |
| `ABA_PAYWAY_CANCEL_URL` | `{FRONTEND_BASE_URL}/bookings` | Where the browser goes when the payer cancels. |

Leaving the merchant ID or API key empty, or setting `ABA_PAYWAY_ENABLED=false`,
keeps the demo flow: `ABA Pay` is recorded as `ABA Pay (Mock)` using the existing
90% success simulation. Wing and card remain demo-only methods. While PayWay is
configured, a client cannot request a simulated ABA success; disable the gateway
to use demo outcomes.

### Sandbox testing

1. Register at [sandbox.payway.com.kh](https://sandbox.payway.com.kh/register-sandbox/)
   and put the emailed merchant ID and API key in `.env`.
2. Restart the backend so Django reloads settings.
3. Approve a booking, open it as the renter, choose **ABA Pay**, and submit the
   hosted checkout form.
4. Complete the sandbox payment. RentEasy reconciles the result when the browser
   returns and continues polling the receipt until PayWay reports a final status.

The browser-return path works on a local machine without a tunnel. PayWay only
accepts a `return_url` (callback) domain that is whitelisted in the merchant
profile; when that is not possible locally, set `ABA_PAYWAY_CALLBACK_URL=` (empty)
to omit `return_url` from the signed form. PayWay then uses the profile default
and RentEasy still reconciles through `continue_success_url` and the refresh API.
To exercise the server-to-server callback as well, expose the backend publicly
and whitelist that domain in the PayWay merchant profile:

```bash
cloudflared tunnel --url http://127.0.0.1:8123
# then set in .env:
# BACKEND_PUBLIC_URL=https://<random>.trycloudflare.com
```

The callback endpoint verifies the `X-PayWay-HMAC-SHA512` header, matches the
transaction to the stored payment, verifies the amount, and is idempotent. Callback
and return reconciliation both use the same guarded confirmation path, so a
duplicate notification cannot double-book or double-notify. If PayWay reports a
second successful charge for a booking that is already paid, the duplicate is
recorded as failed and queued as a pending PayWay refund instead of being hidden.

Common sandbox errors from the purchase API: `1` means the API key/hash is wrong,
`6`/`81` mean the callback or return domain is not whitelisted, and `16`/`19`
mean PayWay rejected the payer name or email.

### Refunds

Refunds for demo (`mock`) payments can be processed in-app. Real ABA PayWay
payments are deliberately **not** refunded by RentEasy: issue the refund in the
PayWay merchant portal (or via PayWay's Refund API), then use **Mark refunded in
PayWay** to record it. That action only updates RentEasy's records and never moves
money.

### Rent hold and owner payouts

Rent is collected into the platform's PayWay account and is **not** forwarded to
the owner automatically:

1. A successful rent payment creates a `Scheduled` payout for the property owner.
2. The money is held for `RENT_HOLD_DAYS` (default **7**). During that window the
   renter or owner can cancel the booking; RentEasy queues a refund and cancels
   the unpaid payout.
3. After the hold, the payout becomes `Eligible` and appears on the owner's
   **Payments** page and in the admin console under **Payments → Owner Payouts**.
4. The owner adds their bank/mobile-money details in **Profile → Payout Account**.
   The admin sends the transfer externally, then clicks **Mark paid** and records
   the transfer reference/note. RentEasy never moves the money itself.
5. Once paid, the payout is final; the booking can no longer be cancelled with an
   automatic refund through the app.

Payout statuses are refreshed on owner/admin list requests, and successful
payments created before this feature are backfilled with payout rows lazily. If
an owner has no payout details, the admin payout action is blocked until they add
them.

Add the hold period to `.env` when you need a shorter or longer review window:

```dotenv
RENT_HOLD_DAYS=7
```

### Payment tests

```bash
cd backend
.venv/bin/python manage.py test
```

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
