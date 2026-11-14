"""Admin-managed integration credentials with environment fallbacks.

Values saved by an admin in ``PlatformSettings`` take precedence over the
process environment so keys can be rotated without restarting the backend.
These helpers perform synchronous ORM reads; async handlers should call them
through ``core.bolt.in_thread``.
"""

from __future__ import annotations

from django.conf import settings
from django.db import OperationalError, ProgrammingError


def platform_value(field: str) -> str:
    """Return one PlatformSettings field, tolerating an unmigrated database."""
    try:
        from accounts.models import PlatformSettings

        value = (
            PlatformSettings.objects.filter(pk=1)
            .values_list(field, flat=True)
            .first()
        )
    except (OperationalError, ProgrammingError):
        return ""
    return str(value or "").strip()


def env_value(setting_name: str) -> str:
    """Return a Django setting as a trimmed string."""
    return str(getattr(settings, setting_name, "") or "").strip()


def _value(field: str, setting_name: str) -> str:
    return platform_value(field) or env_value(setting_name)


def aba_payway_api_key() -> str:
    return _value("aba_payway_api_key", "ABA_PAYWAY_API_KEY")


def google_oauth_client_id() -> str:
    return _value("google_oauth_client_id", "GOOGLE_OAUTH_CLIENT_ID")


def google_oauth_client_secret() -> str:
    return _value("google_oauth_client_secret", "GOOGLE_OAUTH_CLIENT_SECRET")


def google_oauth_redirect_uri() -> str:
    return _value("google_oauth_redirect_uri", "GOOGLE_OAUTH_REDIRECT_URI")


def telegram_bot_token() -> str:
    return _value("telegram_bot_token", "TELEGRAM_BOT_TOKEN")


def telegram_bot_username() -> str:
    return _value("telegram_bot_username", "TELEGRAM_BOT_USERNAME").lstrip("@")


def telegram_webhook_secret() -> str:
    return _value("telegram_webhook_secret", "TELEGRAM_WEBHOOK_SECRET")


def telegram_webhook_url() -> str:
    return _value("telegram_webhook_url", "TELEGRAM_WEBHOOK_URL")


def telegram_chat_id() -> str:
    return _value("telegram_chat_id", "TELEGRAM_CHAT_ID")


def telegram_login_auth_url() -> str:
    return _value("telegram_login_auth_url", "TELEGRAM_LOGIN_AUTH_URL")
