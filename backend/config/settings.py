"""
Django settings for rent_easy_web_django.

RentEasy Web — the web platform companion of the RentEasy Flutter mobile app.
Feature parity with the mobile app, redesigned for the web platform.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-renteasy-web-dev-key-change-me-in-production"

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "[::1]", "testserver"]
ALLOWED_HOSTS += [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if DEBUG:
    ALLOWED_HOSTS.append("*")

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# A TLS-terminating tunnel (ngrok, cloudflared) forwards plain HTTP and sets
# X-Forwarded-Proto: https. Without trusting that header Django builds an
# http:// origin, the browser sends https://, and every POST is rejected with
# "Origin checking failed". run.sh exports both variables when a tunnel is up.
if os.environ.get("TRUST_FORWARDED_PROTO") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS += [
    origin.strip()
    for origin in os.environ.get("EXTRA_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "django_bolt",
    "accounts",
    "core",
    "listings",
    "bookings",
    "payments",
    "notifications",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Phnom_Penh"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = False

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/auth/login/"

DEFAULT_SUPERADMIN = {
    "email": "admin@fake.com",
    "username": "admin",
    "full_name": "RentEasy Admin",
    "password": "admin",
    "role": "superadmin",
}

# -- Rent payouts -------------------------------------------------------------
# A successful rent payment is held by the platform for this many days. During
# the hold either the renter or the owner may cancel (which refunds the renter);
# afterwards the owner's payout becomes eligible for manual transfer.
RENT_HOLD_DAYS = int(os.environ.get("RENT_HOLD_DAYS", "7") or "7")

# -- ABA PayWay ---------------------------------------------------------------
# Sandbox credentials are issued by https://sandbox.payway.com.kh/. When the
# merchant id or API key is missing the payment service falls back to the
# deterministic demo gateway, so local development keeps working.
ABA_PAYWAY_MERCHANT_ID = os.environ.get("ABA_PAYWAY_MERCHANT_ID", "").strip()
ABA_PAYWAY_API_KEY = os.environ.get("ABA_PAYWAY_API_KEY", "").strip()
ABA_PAYWAY_BASE_URL = os.environ.get(
    "ABA_PAYWAY_BASE_URL", "https://checkout-sandbox.payway.com.kh"
).rstrip("/")
_aba_enabled_env = os.environ.get("ABA_PAYWAY_ENABLED")
ABA_PAYWAY_ENABLED = (
    bool(ABA_PAYWAY_MERCHANT_ID and ABA_PAYWAY_API_KEY)
    if _aba_enabled_env is None
    else _aba_enabled_env.strip().lower() in {"1", "true", "yes", "on"}
)
# Empty means "let the hosted checkout page show every option enabled for the
# merchant profile". Set to e.g. ``abapay_khqr`` to force KHQR.
ABA_PAYWAY_PAYMENT_OPTION = os.environ.get("ABA_PAYWAY_PAYMENT_OPTION", "").strip()
ABA_PAYWAY_CURRENCY = os.environ.get("ABA_PAYWAY_CURRENCY", "USD").strip().upper()
ABA_PAYWAY_LIFETIME_MINUTES = int(
    os.environ.get("ABA_PAYWAY_LIFETIME_MINUTES", "30") or "30"
)
ABA_PAYWAY_TIMEOUT_SECONDS = float(
    os.environ.get("ABA_PAYWAY_TIMEOUT_SECONDS", "15") or "15"
)

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:4200").rstrip(
    "/"
)
BACKEND_PUBLIC_URL = os.environ.get(
    "BACKEND_PUBLIC_URL", "http://127.0.0.1:8123"
).rstrip("/")

# PayWay must be able to POST to this URL from the public internet. In local
# development point BACKEND_PUBLIC_URL at an ngrok/cloudflared tunnel; payment
# status is also reconciled through /payments/aba/return/ and the refresh API.
ABA_PAYWAY_CALLBACK_URL = os.environ.get(
    "ABA_PAYWAY_CALLBACK_URL", f"{BACKEND_PUBLIC_URL}/payments/aba/callback/"
)
ABA_PAYWAY_RETURN_URL = os.environ.get(
    "ABA_PAYWAY_RETURN_URL",
    f"{BACKEND_PUBLIC_URL}/payments/aba/return/?payment={{payment_id}}",
)
ABA_PAYWAY_CANCEL_URL = os.environ.get(
    "ABA_PAYWAY_CANCEL_URL", f"{FRONTEND_BASE_URL}/bookings"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
