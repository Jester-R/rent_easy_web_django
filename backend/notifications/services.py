from __future__ import annotations

from django.utils import timezone

from .models import Notification, NotificationSeen
from .default_messages import DEFAULT_NOTIFICATION_MESSAGES


def notify(
    recipient,
    kind: str,
    title_key: str,
    body_key: str,
    *,
    params=None,
    link: str = "",
    action: str = "",
) -> Notification:
    """Create a notification row for ``recipient``."""
    if recipient is None or not getattr(recipient, "pk", None):
        return None
    if not link:
        link = "/notifications/"
    params = dict(params or {})
    message = next(
        (item for item in _notification_messages() if item.get("key") == title_key),
        None,
    )
    if message:
        params["message_overrides"] = {
            "title_en": message.get("title_en", ""),
            "title_km": message.get("title_km", ""),
            "body_en": message.get("body_en", ""),
            "body_km": message.get("body_km", ""),
        }
    return Notification.objects.create(
        recipient=recipient,
        kind=kind,
        title_key=title_key,
        body_key=body_key,
        params=params,
        link=link,
        action=action,
    )


def _notification_messages():
    from accounts.models import PlatformSettings

    configured = (
        PlatformSettings.objects.filter(pk=1)
        .values_list("notification_messages", flat=True)
        .first()
    )
    return (
        configured
        if isinstance(configured, list) and configured
        else DEFAULT_NOTIFICATION_MESSAGES
    )


def mark_all_seen(user) -> None:
    if not user or not user.is_authenticated:
        return
    Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    seen, _ = NotificationSeen.objects.get_or_create(user=user)
    seen.seen_at = timezone.now()
    seen.save(update_fields=["seen_at"])


def unread_for(user):
    if not user or not user.is_authenticated:
        return Notification.objects.none()
    return Notification.objects.filter(recipient=user, read_at__isnull=True)


def unread_count(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    return unread_for(user).count()


def recent_for(user, limit: int = 12):
    if not user or not user.is_authenticated:
        return Notification.objects.none()
    return Notification.objects.filter(recipient=user)[:limit]
