"""
Django settings for rent_easy_web_django.

RentEasy Web — the web platform companion of the RentEasy Flutter mobile app.
Feature parity with the mobile app, redesigned for the web platform.
"""

import os

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "rent_easy_web_django_change_me_in_production"
)
PRODUCTION = bool(os.environ.get("DJANGO_PRODUCTION", False))
SQLITE_PATH = os.environ.get("SQLITE_PATH", "")
MEDIA_PATH = os.environ.get("MEDIA_PATH")

if PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if os.environ.get("TRUST_FORWARDED_PROTO") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "[::1]"]
ALLOWED_HOSTS += [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]


CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

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
        "NAME": SQLITE_PATH,
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

MEDIA_URL = "/media/"
MEDIA_ROOT = MEDIA_PATH

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
# ABA supplies the API key; the merchant ID can be set here or in the admin
# Profile form. Checkout is unavailable until both are configured.
ABA_PAYWAY_MERCHANT_ID = os.environ.get("ABA_PAYWAY_MERCHANT_ID", "").strip()
ABA_PAYWAY_API_KEY = os.environ.get("ABA_PAYWAY_API_KEY", "").strip()
ABA_PAYWAY_BASE_URL = os.environ.get(
    "ABA_PAYWAY_BASE_URL", "https://checkout-sandbox.payway.com.kh"
).rstrip("/")
_aba_enabled_env = os.environ.get("ABA_PAYWAY_ENABLED")
ABA_PAYWAY_ENABLED = (
    bool(ABA_PAYWAY_API_KEY)
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
    "BACKEND_PUBLIC_URL", "http://127.0.0.1:8000"
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

# -- Stripe --------------------------------------------------------------------
# Test-mode ("sandbox") keys look like ``sk_test_...`` / ``pk_test_...`` and are
# created in the Stripe Dashboard under Developers > API keys. Demo payments can
# then be completed with the standard test card 4242 4242 4242 4242. Checkout is
# unavailable until STRIPE_SECRET_KEY is set.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()
# Signing secret of the ``checkout.session.*`` webhook endpoint created in the
# Stripe Dashboard (Developers > Webhooks), e.g. ``whsec_...``. The webhook URL
# must point at {BACKEND_PUBLIC_URL}/payments/stripe/webhook/.
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
_stripe_enabled_env = os.environ.get("STRIPE_ENABLED")
STRIPE_ENABLED = (
    bool(STRIPE_SECRET_KEY)
    if _stripe_enabled_env is None
    else _stripe_enabled_env.strip().lower() in {"1", "true", "yes", "on"}
)
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "USD").strip().lower()
STRIPE_TIMEOUT_SECONDS = float(
    os.environ.get("STRIPE_TIMEOUT_SECONDS", "15") or "15"
)
STRIPE_SESSION_MINUTES = int(
    os.environ.get("STRIPE_SESSION_MINUTES", "30") or "30"
)
# The browser return URL must be reachable publicly. Deployments that serve the
# API behind the frontend's ``/api`` proxy should keep the default below;
# override this when the backend has its own public origin.
STRIPE_RETURN_URL = os.environ.get(
    "STRIPE_RETURN_URL",
    f"{FRONTEND_BASE_URL}/api/payments/stripe/return/?payment={{payment_id}}",
)
STRIPE_CANCEL_URL = os.environ.get(
    "STRIPE_CANCEL_URL", f"{FRONTEND_BASE_URL}/bookings"
)

# -- Google OAuth2 ------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI",
    f"{FRONTEND_BASE_URL}/api/auth/google/callback/",
).strip()
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# -- AI providers -------------------------------------------------------------
AI_PROVIDER = os.environ.get("AI_PROVIDER", "").strip().lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()

# -- Telegram notifications ---------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip()
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_LOGIN_AUTH_URL = os.environ.get(
    "TELEGRAM_LOGIN_AUTH_URL",
    f"{FRONTEND_BASE_URL}/api/auth/telegram/callback/",
).strip()

# -- Email / OTP settings -----------------------------------------------------
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587") or "587")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "RentEasy <noreply@renteasy.com>"
)
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = os.environ.get(
        "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
    )
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


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
