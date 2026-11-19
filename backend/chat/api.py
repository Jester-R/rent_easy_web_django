"""Chat JSON endpoints (renter <-> owner conversations).

Handlers are native async Django-Bolt handlers using the async ORM.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from accounts.models import Role, User
from bookings.models import Booking
from chat.models import Conversation, Message
from core.bolt import (
    body_int,
    body_str,
    in_thread,
    json_body,
    login_required,
    mark_full_request,
    param_int,
    pagination,
    q,
    renter_required,
)
from core.bolt_serializers import conversation as serialize_conversation
from core.bolt_serializers import message_item as serialize_message
from core.bolt_serializers import user_brief as serialize_user_brief
from listings.models import Property
from notifications.models import Notification
from notifications.services import notify
from payments.models import Refund

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)

MAX_MESSAGE = 2000


def _is_admin(user) -> bool:
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "role", "") == Role.SUPERADMIN
    )


def _query_date(request, key: str):
    raw = q(request, key)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _participant_filter(user, participant: str) -> Q:
    if participant == "admin":
        return Q(refund__isnull=False)
    if participant == "owner":
        if _is_admin(user):
            return Q(refund_party="owner")
        if getattr(user, "is_owner", False):
            return Q(owner=user)
        return Q(refund__isnull=True)
    if participant in ("renter", "user"):
        if _is_admin(user):
            return Q(refund_party="renter")
        if getattr(user, "is_renter", False):
            return Q(renter=user)
        return Q(refund__isnull=True)
    return Q()


async def _load_conversation(pk: int, user) -> Conversation:
    conv = (
        await Conversation.objects.select_related(
            "property",
            "renter",
            "owner",
            "refund",
            "refund_participant",
            "support_admin",
        )
        .filter(pk=pk)
        .afirst()
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    if conv.refund_id:
        allowed = user.pk == conv.refund_participant_id or _is_admin(user)
    else:
        allowed = user.pk in (conv.renter_id, conv.owner_id)
    if not allowed:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return conv


async def _notify_new_message(conv: Conversation, sender, message: str) -> None:
    if conv.refund_id:
        if _is_admin(sender):
            recipients = [conv.refund_participant] if conv.refund_participant else []
        elif conv.support_admin:
            recipients = [conv.support_admin]
        else:
            recipients = [
                admin
                async for admin in User.objects.filter(is_active=True)
                .filter(Q(role=Role.SUPERADMIN) | Q(is_staff=True) | Q(is_superuser=True))
                .distinct()
            ]
        title_key = "notif_refund_message"
        body_key = "notif_refund_message_body"
        params = {
            "reference": conv.refund.reference,
            "title": conv.property_title or "your property",
            "sender": sender.display_name,
        }
        action = "refund_message"
    else:
        recipients = [conv.other_party(sender)]
        title_key = "notif_chat_message"
        body_key = "notif_chat_message_body"
        params = {
            "sender": sender.display_name,
            "message": message,
            "title": conv.property_title or "your property",
        }
        action = "chat_message"
    for recipient in recipients:
        await in_thread(
            notify,
            recipient,
            Notification.Kind.CHAT_MESSAGE,
            title_key,
            body_key,
            params=params,
            link=f"/messages/{conv.pk}",
            action=action,
        )


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
    visible = Q(refund__isnull=True) & (Q(renter=user) | Q(owner=user))
    if _is_admin(user):
        visible |= Q(refund__isnull=False)
    else:
        visible |= Q(refund__isnull=False, refund_participant=user)
    chat_type = q(request, "chat_type", "all")
    if chat_type == "refund":
        visible &= Q(refund__isnull=False)
    elif chat_type == "general":
        visible &= Q(refund__isnull=True)

    participant = q(request, "participant", "all")
    if participant in ("admin", "owner", "renter", "user"):
        visible &= _participant_filter(user, participant)

    property_query = q(request, "property")
    if property_query:
        visible &= Q(property__title__icontains=property_query) | Q(
            property__location__icontains=property_query
        )

    date_from = _query_date(request, "date_from")
    date_to = _query_date(request, "date_to")
    if date_from:
        visible &= Q(updated_at__date__gte=date_from)
    if date_to:
        visible &= Q(updated_at__date__lte=date_to)

    search = q(request, "search")
    if search:
        visible &= (
            Q(property__title__icontains=search)
            | Q(property__location__icontains=search)
            | Q(renter__full_name__icontains=search)
            | Q(renter__username__icontains=search)
            | Q(renter__email__icontains=search)
            | Q(owner__full_name__icontains=search)
            | Q(owner__username__icontains=search)
            | Q(owner__email__icontains=search)
            | Q(refund_participant__full_name__icontains=search)
            | Q(refund_participant__username__icontains=search)
            | Q(refund_participant__email__icontains=search)
            | Q(support_admin__full_name__icontains=search)
            | Q(support_admin__username__icontains=search)
            | Q(support_admin__email__icontains=search)
            | Q(refund__reference__icontains=search)
        )

    queryset = (
        Conversation.objects.select_related(
            "property",
            "renter",
            "owner",
            "refund",
            "refund_participant",
            "support_admin",
        )
        .filter(visible)
        .order_by(
            Case(
                When(refund__isnull=False, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-updated_at",
            "-pk",
        )
    )
    total = await queryset.acount()
    page, page_size = pagination(
        request, default_size=20, page_key="page", size_key="page_size"
    )
    rows = queryset[(page - 1) * page_size : page * page_size]
    return {
        "conversations": [await _summary(c, user) async for c in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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
        await _notify_new_message(conv, user, body)
    return {"conversation": await _summary(conv, user)}


@api.post("/bookings/{pk}/chat/")
async def booking_chat(request):
    user = await login_required(request)
    pk = param_int(request, "pk")
    booking = (
        await Booking.objects.select_related("property", "renter", "owner")
        .filter(pk=pk)
        .afirst()
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="booking_not_found")
    if user.pk not in (booking.renter_id, booking.owner_id):
        raise HTTPException(status_code=403, detail="not_authorized")

    conv, _created = await Conversation.objects.aget_or_create(
        property=booking.property,
        renter=booking.renter,
        owner=booking.owner,
        refund=None,
    )
    conv = (
        await Conversation.objects.select_related("property", "renter", "owner")
        .filter(pk=conv.pk)
        .afirst()
    )
    return {"conversation": await _summary(conv, user)}


@api.get("/conversations/{pk}/messages/")
async def conversation_messages(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    conv = await _load_conversation(pk, user)
    await (
        conv.messages.filter(read_at__isnull=True)
        .exclude(sender_id=user.pk)
        .aupdate(read_at=timezone.now())
    )
    queryset = conv.messages.select_related("sender").order_by("-created_at", "-pk")
    total = await queryset.acount()
    page, page_size = pagination(
        request, default_size=50, page_key="page", size_key="page_size"
    )
    items = [m async for m in queryset[(page - 1) * page_size : page * page_size]]
    items.reverse()
    other = conv.other_party(user)
    return {
        "messages": [await serialize_message(m) for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
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
    if (
        conv.refund_id
        and _is_admin(user)
        and conv.refund.status
        not in (Refund.Status.ACCEPTED, Refund.Status.PROCESSED)
    ):
        raise HTTPException(status_code=409, detail="refund_not_accepted")
    msg = await Message.objects.acreate(
        conversation=conv, sender=user, body=body[:MAX_MESSAGE]
    )
    conv.updated_at = timezone.now()
    await conv.asave(update_fields=["updated_at"])
    await _notify_new_message(conv, user, msg.body)
    return {"message": await serialize_message(msg)}


@api.post("/conversations/{pk}/read/")
async def mark_read(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    conv = await _load_conversation(pk, user)
    await (
        conv.messages.filter(read_at__isnull=True)
        .exclude(sender_id=user.pk)
        .aupdate(read_at=timezone.now())
    )
    return {"ok": True, "unread": 0}


mark_full_request(api)

__all__ = ["api"]
