"""Optional Telegram delivery for the application's in-app notifications."""

from __future__ import annotations

import logging

import httpx

from accounts.integration_config import telegram_bot_token, telegram_chat_id

from .models import Notification
from .rendering import notification_copy, render

logger = logging.getLogger(__name__)


def _message_text(notification: Notification) -> str:
    copy = notification_copy(notification)
    params = copy.get("params") or {}
    text = (
        "RentEasy notification\n"
        f"{render(copy['title_en'], params)}\n{render(copy['body_en'], params)}"
    )
    if copy["title_km"] or copy["body_km"]:
        text += (
            f"\n\n{render(copy['title_km'], params)}"
            f"\n{render(copy['body_km'], params)}"
        )
    return text[:4096]


def send_telegram_notification(notification_id: int) -> None:
    """Mirror an in-app notification to its linked Telegram account."""
    token = telegram_bot_token()
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
        chat_id = telegram_chat_id()
    if not chat_id:
        return

    send_telegram_message(chat_id, _message_text(notification))


def send_telegram_message(chat_id: str, text: str) -> bool:
    token = telegram_bot_token()
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
