"""Shared rendering for notification delivery channels (Telegram, email)."""

from __future__ import annotations

from typing import Any

from .models import Notification


class _SafeFormat(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format_map(_SafeFormat(params))
    except (KeyError, ValueError):
        return template


def notification_copy(notification: Notification) -> dict[str, Any]:
    """Return the localized title/body copy for a notification."""
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
    return {
        "title_en": str(
            overrides.get("title_en")
            or configured.get("title_en")
            or notification.get_kind_display()
        ),
        "body_en": str(
            overrides.get("body_en")
            or configured.get("body_en")
            or notification.body_key
        ),
        "title_km": str(
            overrides.get("title_km") or configured.get("title_km") or ""
        ),
        "body_km": str(overrides.get("body_km") or configured.get("body_km") or ""),
        "params": params,
    }
