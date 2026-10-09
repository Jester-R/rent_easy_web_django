"""Chat JSON endpoints (renter <-> owner conversations).

Handlers are native async Django-Bolt handlers using the async ORM.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from chat.models import Conversation, Message
from core.bolt import (
    body_int,
    body_str,
    json_body,
    login_required,
    mark_full_request,
    param_int,
    renter_required,
)
from core.bolt_serializers import conversation as serialize_conversation
from core.bolt_serializers import message_item as serialize_message
from core.bolt_serializers import user_brief as serialize_user_brief
from listings.models import Property

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)

MAX_MESSAGE = 2000


async def _load_conversation(pk: int, user) -> Conversation:
    conv = (
        await Conversation.objects.select_related("property", "renter", "owner")
        .filter(pk=pk)
        .afirst()
    )
    if conv is None or user.pk not in (conv.renter_id, conv.owner_id):
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return conv


async def _summary(conv: Conversation, user) -> dict:
    last = await conv.messages.order_by("-created_at").afirst()
    unread = (
        await conv.messages.filter(read_at__isnull=True)
        .exclude(sender_id=user.pk)
        .acount()
    )
    other = conv.other_party(user)
    return await serialize_conversation(
        conv,
        other_party=await serialize_user_brief(other),
        last_message=last.body if last else "",
        last_message_at=(last.created_at if last else conv.created_at),
        unread=unread,
    )


@api.get("/conversations/")
async def conversations(request):
    user = await login_required(request)
    rows = [
        c
        async for c in Conversation.objects.select_related(
            "property", "renter", "owner"
        ).filter(Q(renter=user) | Q(owner=user))
    ]
    return {"conversations": [await _summary(c, user) for c in rows]}


@api.post("/conversations/")
async def start_conversation(request):
    user = await renter_required(request)
    data = json_body(request)
    property_id = body_int(data, "property_id", 0)
    prop = (
        await Property.objects.select_related("owner")
        .filter(pk=property_id, is_active=True)
        .afirst()
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="property_not_found")
    if prop.owner_id == user.pk:
        raise HTTPException(status_code=422, detail="cannot_message_self")

    conv, _created = await Conversation.objects.aget_or_create(
        property=prop, renter=user, owner=prop.owner
    )
    conv = (
        await Conversation.objects.select_related("property", "renter", "owner")
        .filter(pk=conv.pk)
        .afirst()
    )
    body = body_str(data, "message").strip()
    if body:
        await Message.objects.acreate(
            conversation=conv, sender=user, body=body[:MAX_MESSAGE]
        )
        conv.updated_at = timezone.now()
        await conv.asave(update_fields=["updated_at"])
    return {"conversation": await _summary(conv, user)}


@api.get("/conversations/{pk}/messages/")
async def conversation_messages(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    conv = await _load_conversation(pk, user)
    await conv.messages.filter(read_at__isnull=True).exclude(
        sender_id=user.pk
    ).aupdate(read_at=timezone.now())
    items = [
        m
        async for m in conv.messages.select_related("sender").order_by("created_at")
    ]
    other = conv.other_party(user)
    return {
        "messages": [await serialize_message(m) for m in items],
        "conversation": await _summary(conv, user),
        "other_party": await serialize_user_brief(other),
    }


@api.post("/conversations/{pk}/messages/")
async def send_message(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    conv = await _load_conversation(pk, user)
    data = json_body(request)
    body = body_str(data, "body").strip()
    if not body:
        raise HTTPException(status_code=422, detail="message_required")
    msg = await Message.objects.acreate(
        conversation=conv, sender=user, body=body[:MAX_MESSAGE]
    )
    conv.updated_at = timezone.now()
    await conv.asave(update_fields=["updated_at"])
    return {"message": await serialize_message(msg)}


@api.post("/conversations/{pk}/read/")
async def mark_read(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    conv = await _load_conversation(pk, user)
    await conv.messages.filter(read_at__isnull=True).exclude(
        sender_id=user.pk
    ).aupdate(read_at=timezone.now())
    return {"ok": True, "unread": 0}


mark_full_request(api)

__all__ = ["api"]
