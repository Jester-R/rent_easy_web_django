from __future__ import annotations

from django.utils.functional import SimpleLazyObject


def unread_notifications(request):
    """Unread badge counter for the topbar bell.

    Exposed as a lazy object so anonymous requests never hit the database.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"UNREAD_NOTIFICATIONS": 0, "unread_count": 0, "HAS_UNREAD": False}

    def _count() -> int:
        from .services import unread_count

        return unread_count(user)

    count = SimpleLazyObject(_count)
    return {"UNREAD_NOTIFICATIONS": count, "unread_count": count, "HAS_UNREAD": count}
