# RentEasy Web (Django Platform)

> A full-featured real estate rental platform built with Django 6 and Tailwind CSS. Web companion to the **RentEasy Mobile App** (`rent_easy.ipa`), offering complete feature parity redesigned for web browsers.

---

## Features

- **Multi-Role Portals**:
  - **Renter**: Property discovery, advanced filtering (location, price, rooms), bookmarking favorites, rental booking requests, and mock checkout.
  - **Property Owner**: Listing management (CRUD), tenant application review, booking approval/rejection, income tracking, and refund processing.
  - **Superadmin Console**: System analytics, revenue metrics, booking funnels, global CRUD, bulk deletions, and audit trails.
- **Bilingual (i18n)**: Instant switching between **English** and **Khmer (ភាសាខ្មែរ)** with persistent cookies.
- **Theming**: Integrated **Light** and **Dark** mode with zero-flash pre-render initialization.
- **Mock Payments & Refunds**: Support for ABA Pay Mock, Wing Mock, and Credit Card Mock with automated refund generation.
- **Notifications**: In-app notifications with unread badge counter and dropdown feed.

---

## Tech Stack

- **Backend**: Python 3.12+, Django 6.1.1, SQLite (WAL mode + NORMAL synchronous PRAGMA), WhiteNoise 6.12.0
- **Frontend**: Tailwind CSS 4.3.3, jQuery 4.0.0 (slim), inline SVG icon engine
- **Testing & Tooling**: Puppeteer Core 25.12.0 for E2E tests, Ngrok tunnel integration

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+ (for Tailwind CSS asset builds and Puppeteer tests)

### Quick Start

Using the automated runner:
```bash
./run.sh                 # Starts server on :8010 + public ngrok URL (if configured)
./run.sh --no-ngrok      # Starts server locally on http://localhost:8010
./run.sh --reset         # Reseeds demo accounts & listings before starting
```

### Manual Setup

1. **Activate Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   npm install
   ```

3. **Run Migrations & Seed Data**:
   ```bash
   python manage.py migrate
   python manage.py seed_demo --reset
   ```

4. **Build Frontend Assets**:
   ```bash
   npm run build:css
   ```

5. **Start Development Server**:
   ```bash
   python manage.py runserver 0.0.0.0:8010
   ```

---

## Demo Accounts

| Role | Username / Identifier | Password | Default Portal |
| :--- | :--- | :--- | :--- |
| **Superadmin** | `admin@fake.com` (`admin`) | `admin` | `/console/` |
| **Owner** | `owner@fake.com` (`owner`) | `owner` | `/owner/` |
| **Renter** | `renter@fake.com` (`renter`) | `renter` | `/rent/` |

---

## Testing & Quality Assurance

- **End-to-End Functional Test**:
  ```bash
  node tools/func_check.mjs
  ```
- **Responsive Viewport Audit**:
  ```bash
  node tools/audit_responsive.mjs
  ```
