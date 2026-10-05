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
ALLOWED_HOSTS += [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "core",
    "listings",
    "bookings",
    "payments",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ThemeMiddleware",
    "core.middleware.LanguageMiddleware",
    "core.middleware.FlashMiddleware",
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
                "core.context_processors.site",
                "core.context_processors.i18n_context",
                "core.context_processors.js_config",
                "notifications.context_processors.unread_notifications",
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

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

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
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
