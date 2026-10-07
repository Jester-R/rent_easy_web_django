"""Notifications JSON endpoints (bell feed, badge, read state).

Handlers are native async Django-Bolt handlers; only the sync notification
services hop through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from django_bolt import BoltAPI

from core.bolt import in_thread, login_required, mark_full_request, param_int
from core.bolt_serializers import notification as serialize_notification
from notifications.models import Notification
from notifications.services import mark_all_seen, recent_for, unread_count

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


@api.get("/notifications/")
async def feed(request):
    user = await login_required(request)
    items = [
        await serialize_notification(item)
        async for item in recent_for(user, limit=60)
    ]
    await in_thread(mark_all_seen, user)
    return {"notifications": items, "unread": 0}


@api.get("/notifications/preview/")
async def preview(request):
    user = await login_required(request)
    items = [
        await serialize_notification(item)
        async for item in recent_for(user, limit=12)
    ]
    return {"items": items, "unread": await in_thread(unread_count, user)}


@api.get("/notifications/badge/")
async def badge(request):
    user = await login_required(request)
    return {"unread": await in_thread(unread_count, user)}


@api.post("/notifications/read-all/")
async def read_all(request):
    user = await login_required(request)
    await in_thread(mark_all_seen, user)
    return {"ok": True, "unread": 0}


@api.post("/notifications/mark-seen/")
async def mark_seen(request):
    user = await login_required(request)
    await in_thread(mark_all_seen, user)
    return {"ok": True, "unread": 0}


@api.post("/notifications/{pk}/toggle-read/")
async def toggle_read(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    item = await Notification.objects.filter(pk=pk, recipient=user).afirst()
    if item is not None:
        await in_thread(item.mark_read)
    return {"ok": item is not None, "read": item.is_read if item else False}


mark_full_request(api)

__all__ = ["api"]