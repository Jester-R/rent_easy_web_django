"""Notifications JSON endpoints (bell feed, badge, read state).

Handlers are native async Django-Bolt handlers; only the sync notification
services hop through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

import asyncio

from django_bolt import BoltAPI
from django_bolt.responses import EventSourceResponse, ServerSentEvent

from core.bolt import (
    in_thread,
    login_required,
    mark_full_request,
    pagination,
    param_int,
    q,
)
from core.bolt_serializers import notification as serialize_notification
from notifications.models import Notification
from notifications.services import mark_all_seen, recent_for, unread_count

STREAM_POLL_SECONDS = 3.0
STREAM_BATCH = 25

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


@api.get("/notifications/")
async def feed(request):
    user = await login_required(request)
    page, page_size = pagination(request)
    queryset = Notification.objects.filter(recipient=user).order_by(
        "-created_at", "-pk"
    )
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]
    items = [await serialize_notification(item) async for item in queryset]
    await in_thread(mark_all_seen, user)
    return {
        "notifications": items,
        "unread": 0,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@api.get("/notifications/preview/")
async def preview(request):
    user = await login_required(request)
    items = [
        await serialize_notification(item) async for item in recent_for(user, limit=12)
    ]
    return {"items": items, "unread": await in_thread(unread_count, user)}


@api.get("/notifications/badge/")
async def badge(request):
    user = await login_required(request)
    return {"unread": await in_thread(unread_count, user)}


@api.get("/notifications/stream/")
async def stream(request):
    """Server-Sent Events feed of new notifications for the signed-in user.

    SSE is a better fit than WebSockets here: notifications are one-way
    server -> client, and browsers reconnect ``EventSource`` automatically.
    The generator polls the notification table (rather than an in-process
    queue) so it keeps working when several server workers are running.
    """
    user = await login_required(request)
    user_id = user.pk

    raw_after = q(request, "after")
    try:
        last_id = int(raw_after)
    except TypeError, ValueError:
        last_id = (
            await Notification.objects.filter(recipient_id=user_id)
            .order_by("-pk")
            .values_list("pk", flat=True)
            .afirst()
        ) or 0

    unread = await in_thread(unread_count, user)

    async def events():
        nonlocal last_id
        yield ServerSentEvent(
            event="ready",
            data={"unread": unread, "last_id": last_id},
        )
        while True:
            await asyncio.sleep(STREAM_POLL_SECONDS)
            rows = [
                item
                async for item in Notification.objects.filter(
                    recipient_id=user_id, pk__gt=last_id
                ).order_by("pk")[:STREAM_BATCH]
            ]
            for item in rows:
                last_id = item.pk
                yield ServerSentEvent(
                    event="notification",
                    id=str(item.pk),
                    data=await serialize_notification(item),
                )

    return EventSourceResponse(
        events(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
