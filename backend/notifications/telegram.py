"""Optional Telegram delivery for the application's in-app notifications."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from django.conf import settings

from .models import Notification

logger = logging.getLogger(__name__)


class _SafeFormat(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format_map(_SafeFormat(params))
    except KeyError, ValueError:
        return template


def _message_text(notification: Notification) -> str:
    params = notification.params if isinstance(notification.params, dict) else {}
    overrides = params.get("message_overrides", {})
    overrides = overrides if isinstance(overrides, dict) else {}
    from .services import _notification_messages

    configured = next(
        (
            item
            for item in _notification_messages()
            if item.get("key") == notification.title_key
        ),
        {},
    )
    title_en = (
        overrides.get("title_en")
        or configured.get("title_en")
        or notification.get_kind_display()
    )
    body_en = (
        overrides.get("body_en") or configured.get("body_en") or notification.body_key
    )
    title_km = overrides.get("title_km") or configured.get("title_km") or ""
    body_km = overrides.get("body_km") or configured.get("body_km") or ""
    text = (
        "RentEasy notification\n"
        f"{_render(str(title_en), params)}\n{_render(str(body_en), params)}"
    )
    if title_km or body_km:
        text += f"\n\n{_render(str(title_km), params)}\n{_render(str(body_km), params)}"
    return text[:4096]


def send_telegram_notification(notification_id: int) -> None:
    """Mirror an in-app notification to its linked Telegram account."""
    token = (
        getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    )
    if not token:
        return

    notification = (
        Notification.objects.filter(pk=notification_id)
        .select_related("recipient")
        .first()
    )
    if notification is None:
        return

    chat_id = notification.recipient.telegram_chat_id
    # A shared admin chat remains an optional fallback for staff notifications.
    if not chat_id and (
        notification.recipient.is_staff or notification.recipient.is_superuser
    ):
        chat_id = (
            getattr(settings, "TELEGRAM_CHAT_ID", "")
            or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        )
    if not chat_id:
        return

    send_telegram_message(chat_id, _message_text(notification))


def send_telegram_message(chat_id: str, text: str) -> bool:
    token = (
        getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    )
    if not token or not chat_id:
        return False

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4096]},
            timeout=5.0,
        )
        response.raise_for_status()
        if not response.json().get("ok"):
            logger.warning("Telegram rejected a notification delivery")
            return False
        return True
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # Telegram delivery is best-effort and must not break the in-app feed.
        logger.warning("Telegram notification delivery failed (%s)", type(exc).__name__)
        return False
