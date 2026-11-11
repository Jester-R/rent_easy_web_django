"""Account activity notifications for the in-app bell and external channels."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from accounts.models import Role, User
from notifications.models import Notification
from notifications.services import notify


def _can_notify(recipient) -> bool:
    return recipient is not None and bool(getattr(recipient, "pk", None))


def notify_account_created(recipient, provider: str) -> None:
    """Tell a user that their new account is ready."""
    if not _can_notify(recipient):
        return
    notify(
        recipient,
        Notification.Kind.ACCOUNT_CREATED,
        "notif_account_created",
        "notif_account_created_body",
        params={"provider": provider, "name": recipient.display_name},
        link="/notifications/",
    )


def notify_account_signed_in(recipient, provider: str) -> None:
    """Record each successful sign-in in the user's bell feed."""
    if not _can_notify(recipient):
        return
    notify(
        recipient,
        Notification.Kind.ACCOUNT_SIGN_IN,
        "notif_account_signed_in",
        "notif_account_signed_in_body",
        params={
            "provider": provider,
            "time": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
        },
        link="/notifications/",
    )


def notify_admins_of_telegram_registration(user: User) -> None:
    """Alert staff/superadmins when an account is created through Telegram."""
    if not _can_notify(user):
        return
    admins = User.objects.filter(
        Q(role=Role.SUPERADMIN) | Q(is_superuser=True) | Q(is_staff=True)
    ).distinct()
    for admin in admins:
        if admin.pk == user.pk:
            continue
        notify(
            admin,
            Notification.Kind.TELEGRAM_REGISTRATION,
            "notif_telegram_registration",
            "notif_telegram_registration_body",
            params={
                "name": user.display_name,
                "email": user.email,
                "telegram": user.telegram_id or "",
            },
            link="/console/users/",
            action="telegram_registration",
        )
