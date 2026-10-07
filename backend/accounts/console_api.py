"""Superadmin console JSON endpoints (mounted under ``/console``).

This module intentionally defines its own :class:`BoltAPI` named
``console_api`` (not ``api``) so django-bolt's auto-discovery does not pick it
up as a standalone app API; it is mounted by :mod:`accounts.api`.

Handlers are native async Django-Bolt handlers; the synchronous
payment/notification services and manager helpers hop through
:func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from accounts.models import AuditLog, Role, User, is_valid_username, normalize_identity
from bookings.models import Booking, BookingStatus
from core.bolt import (
    body_bool,
    body_float,
    body_int,
    body_str,
    in_thread,
    json_body,
    mark_full_request,
    param_int,
    superadmin_required,
)
from core.bolt_serializers import audit as serialize_audit
from core.bolt_serializers import booking as serialize_booking
from core.bolt_serializers import payment as serialize_payment
from core.bolt_serializers import property as serialize_property
from core.bolt_serializers import refund as serialize_refund
from core.bolt_serializers import user as serialize_user
from listings.models import Favorite, Property
from payments.models import Payment, Refund
from payments.services import process_refund

console_api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


async def audit(actor, action: str, entity: str, entity_id, summary: str = "") -> None:
    await AuditLog.objects.acreate(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        summary=summary[:255],
    )


def _ids(data: dict) -> list[int]:
    raw = data.get("ids") or []
    if isinstance(raw, str):
        raw = [part for part in raw.split(",") if part.strip()]
    out = []
    for value in raw:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


def _optional_id(data: dict, key: str):
    value = data.get(key)
    if value in (None, "", "null"):
        return None
    return body_int(data, key, 0) or None


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_date") from exc


def _not_found(kind: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind}_not_found")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@console_api.get("/")
async def dashboard(request):
    await superadmin_required(request)
    payments_qs = Payment.objects.all()

    revenue = (
        await payments_qs.filter(status=Payment.Status.SUCCESS).aaggregate(
            v=Sum("amount")
        )
    )["v"] or 0
    refunded = (await payments_qs.aaggregate(v=Sum("refunded_amount")))["v"] or 0
    avg_rent = (await Property.objects.aaggregate(v=Avg("price_per_month")))["v"] or 0

    monthly_rows = [
        row
        async for row in payments_qs.filter(status=Payment.Status.SUCCESS)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("month")
    ]
    for row in monthly_rows:
        row["month"] = row["month"].isoformat() if row["month"] else None
        row["total"] = float(row["total"] or 0)

    status_counts = {
        row["status"]: row["n"]
        async for row in Booking.objects.values("status").annotate(n=Count("id"))
    }
    top_properties = Property.objects.select_related("owner").annotate(
        revenue=Sum(
            "payments__amount", filter=Q(payments__status=Payment.Status.SUCCESS)
        ),
        bookings_total=Count("bookings", distinct=True),
        favorites_total=Count("favorites", distinct=True),
    ).order_by("-revenue")[:6]

    return {
        "stats": {
            "users": await User.objects.acount(),
            "owners": await User.objects.filter(role=Role.OWNER).acount(),
            "renters": await User.objects.filter(role=Role.RENTER).acount(),
            "properties": await Property.objects.acount(),
            "bookings": await Booking.objects.acount(),
            "payments": await Payment.objects.acount(),
            "favorites": await Favorite.objects.acount(),
            "refunds": await Refund.objects.acount(),
            "pending_refunds": await Refund.objects.filter(
                status=Refund.Status.PENDING
            ).acount(),
            "revenue": float(revenue),
            "refunded": float(refunded),
            "avg_rent": float(avg_rent),
        },
        "status_counts": status_counts,
        "monthly_rows": monthly_rows,
        "top_properties": [
            await serialize_property(
                p,
                revenue=float(p.revenue if getattr(p, "revenue", None) is not None else 0),
                booking_count=p.bookings_total,
                favorite_count=p.favorites_total,
            )
            async for p in top_properties
        ],
        "role_breakdown": [
            row
            async for row in User.objects.values("role")
            .annotate(n=Count("id"))
            .order_by("-n")
        ],
        "recent_bookings": [
            await serialize_booking(b)
            async for b in Booking.objects.select_related("property", "renter", "owner")
            .order_by("-created_at")[:8]
        ],
        "recent_users": [
            await serialize_user(u)
            async for u in User.objects.order_by("-date_joined")[:6]
        ],
        "audit_logs": [
            await serialize_audit(a)
            async for a in AuditLog.objects.select_related("actor")[:8]
        ],
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@console_api.get("/users/")
async def users_list(request):
    await superadmin_required(request)
    from core.bolt import q

    query = q(request, "q")
    role = q(request, "role", "all")
    queryset = User.objects.all().order_by("-date_joined")
    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(username__icontains=query)
        )
    if role in dict(Role.choices):
        queryset = queryset.filter(role=role)
    queryset = queryset.annotate(
        property_count=Count("properties", distinct=True),
        booking_count=Count("renters_bookings", distinct=True),
    )
    return {
        "users": [
            await serialize_user(u) | {"property_count": u.property_count, "booking_count": u.booking_count}
            async for u in queryset
        ],
        "query": query,
        "role": role,
        "roles": [{"value": v, "label": label} for v, label in Role.choices],
        "total": await User.objects.acount(),
    }


@console_api.get("/users/{pk}/")
async def user_detail(request):
    pk = param_int(request, "pk")
    await superadmin_required(request)
    user = await User.objects.filter(pk=pk).afirst()
    if user is None:
        raise _not_found("user")
    return {"user": await serialize_user(user)}


@console_api.post("/users/new/")
async def user_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    email = normalize_identity(body_str(data, "email"))
    username = body_str(data, "username")
    password = body_str(data, "password")
    role = body_str(data, "role") or Role.RENTER

    if not email:
        raise HTTPException(status_code=422, detail="email_required")
    if not password:
        raise HTTPException(status_code=422, detail="password_too_short")
    if not is_valid_username(username):
        raise HTTPException(status_code=422, detail="username_invalid")
    if role not in dict(Role.choices):
        raise HTTPException(status_code=422, detail="role_invalid")
    if await User.objects.filter(email__iexact=email).aexists():
        raise HTTPException(status_code=409, detail="email_taken")
    if await User.objects.filter(username__iexact=username).aexists():
        raise HTTPException(status_code=409, detail="username_taken")

    user = await in_thread(
        User.objects.create_user,
        email=email,
        username=username,
        password=password,
        full_name=body_str(data, "full_name"),
        role=role,
        is_active=body_bool(data, "is_active", True),
    )
    await audit(actor, AuditLog.Action.CREATE, "user", user.pk, f"created {user.email}")
    return {"user": await serialize_user(user)}


@console_api.post("/users/{pk}/edit/")
async def user_edit(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    user = await User.objects.filter(pk=pk).afirst()
    if user is None:
        raise _not_found("user")
    data = json_body(request)

    if "email" in data:
        email = normalize_identity(body_str(data, "email"))
        if await User.objects.filter(email__iexact=email).exclude(pk=user.pk).aexists():
            raise HTTPException(status_code=409, detail="email_taken")
        user.email = email
    if "username" in data:
        username = body_str(data, "username")
        if not is_valid_username(username):
            raise HTTPException(status_code=422, detail="username_invalid")
        if await User.objects.filter(username__iexact=username).exclude(pk=user.pk).aexists():
            raise HTTPException(status_code=409, detail="username_taken")
        user.username = username
    if "full_name" in data:
        user.full_name = body_str(data, "full_name")
    if "role" in data:
        role = body_str(data, "role")
        if role not in dict(Role.choices):
            raise HTTPException(status_code=422, detail="role_invalid")
        user.role = role
    if "is_active" in data:
        user.is_active = body_bool(data, "is_active", user.is_active)

    password = body_str(data, "password")
    if password:
        await in_thread(user.set_password, password)
    await user.asave()
    await audit(actor, AuditLog.Action.UPDATE, "user", user.pk, f"updated {user.email}")
    return {"user": await serialize_user(user)}


@console_api.post("/users/{pk}/delete/")
async def user_delete(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    user = await User.objects.filter(pk=pk).afirst()
    if user is None:
        raise _not_found("user")
    if user.pk == actor.pk:
        raise HTTPException(status_code=409, detail="not_authorized")
    label = user.email
    await user.adelete()
    await audit(actor, AuditLog.Action.DELETE, "user", pk, f"deleted {label}")
    return {"ok": True, "deleted": pk}


@console_api.post("/users/bulk-delete/")
async def users_bulk_delete(request):
    actor = await superadmin_required(request)
    ids = _ids(json_body(request))
    deleted = 0
    for user_id in ids:
        if user_id == actor.pk:
            continue
        if (await User.objects.filter(pk=user_id).adelete())[0]:
            deleted += 1
    await audit(
        actor,
        AuditLog.Action.DELETE,
        "user",
        ",".join(map(str, ids)),
        f"bulk deleted {deleted}",
    )
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@console_api.get("/properties/")
async def properties_list(request):
    await superadmin_required(request)
    from core.bolt import q

    query = q(request, "q")
    owner = q(request, "owner")
    queryset = Property.objects.select_related("owner").order_by("-created_at")
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(location__icontains=query)
            | Q(owner__email__icontains=query)
        )
    if owner:
        queryset = queryset.filter(owner_id=owner)
    queryset = queryset.annotate(
        favorite_count=Count("favorites", distinct=True),
        booking_count=Count("bookings", distinct=True),
    )
    return {
        "properties": [
            await serialize_property(
                p,
                favorite_count=p.favorite_count,
                booking_count=p.booking_count,
            )
            async for p in queryset
        ],
        "query": query,
        "owner": owner,
        "owners": [
            await serialize_user(u)
            async for u in User.objects.filter(role=Role.OWNER).order_by("full_name")
        ],
        "total": await Property.objects.acount(),
    }


def _property_fields(data: dict) -> dict:
    title = body_str(data, "title")
    location = body_str(data, "location")
    price = body_float(data, "price_per_month")
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    if not location:
        raise HTTPException(status_code=422, detail="location_required")
    if price is None or price <= 0:
        raise HTTPException(status_code=422, detail="price_required")
    return {
        "title": title,
        "location": location,
        "price_per_month": Decimal(str(price)),
        "bedrooms": max(0, body_int(data, "bedrooms", 0)),
        "bathrooms": max(0, body_int(data, "bathrooms", 0)),
        "description": body_str(data, "description"),
    }


@console_api.post("/properties/new/")
async def property_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    owner = await User.objects.filter(
        pk=_optional_id(data, "owner"), role=Role.OWNER
    ).afirst()
    if owner is None:
        raise HTTPException(status_code=422, detail="owner_required")
    prop = await Property.objects.acreate(owner=owner, **_property_fields(data))
    await audit(actor, AuditLog.Action.CREATE, "property", prop.pk, f"created {prop.title}")
    return {"property": await serialize_property(prop)}


@console_api.post("/properties/{pk}/edit/")
async def property_edit(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    prop = await Property.objects.filter(pk=pk).afirst()
    if prop is None:
        raise _not_found("property")
    data = json_body(request)
    for field, value in _property_fields(data).items():
        setattr(prop, field, value)
    owner_id = _optional_id(data, "owner")
    if owner_id:
        owner = await User.objects.filter(pk=owner_id, role=Role.OWNER).afirst()
        if owner is not None:
            prop.owner = owner
    await prop.asave()
    await audit(actor, AuditLog.Action.UPDATE, "property", prop.pk, f"updated {prop.title}")
    return {"property": await serialize_property(prop)}


@console_api.post("/properties/{pk}/delete/")
async def property_delete(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    prop = await Property.objects.filter(pk=pk).afirst()
    if prop is None:
        raise _not_found("property")
    title = prop.title
    await prop.adelete()
    await audit(actor, AuditLog.Action.DELETE, "property", pk, f"deleted {title}")
    return {"ok": True, "deleted": pk}


@console_api.post("/properties/bulk-delete/")
async def properties_bulk_delete(request):
    actor = await superadmin_required(request)
    ids = _ids(json_body(request))
    await Property.objects.filter(pk__in=ids).adelete()
    await audit(
        actor,
        AuditLog.Action.DELETE,
        "property",
        ",".join(map(str, ids)),
        "bulk deleted properties",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


@console_api.get("/bookings/")
async def bookings_list(request):
    await superadmin_required(request)
    from bookings.helpers import (
        apply_status_filter,
        booking_all_queryset,
        search_bookings,
    )
    from core.bolt import q

    query = q(request, "q")
    status = q(request, "status", "all")
    queryset = search_bookings(
        apply_status_filter(booking_all_queryset(), status), query
    )

    status_counts = {"all": await Booking.objects.acount()}
    async for row in Booking.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    return {
        "bookings": [await serialize_booking(b) async for b in queryset],
        "query": query,
        "status": status,
        "status_counts": status_counts,
        "total": await Booking.objects.acount(),
    }


@console_api.post("/bookings/new/")
async def booking_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    prop = await Property.objects.filter(pk=_optional_id(data, "property")).afirst()
    renter = await User.objects.filter(pk=_optional_id(data, "renter")).afirst()
    if prop is None or renter is None:
        raise HTTPException(status_code=422, detail="property_and_renter_required")
    owner_id = _optional_id(data, "owner")
    owner = await User.objects.filter(pk=owner_id).afirst() if owner_id else None
    if owner is None:
        owner = await User.objects.filter(pk=prop.owner_id).afirst()
    status = body_str(data, "status") or BookingStatus.PENDING
    if status not in dict(BookingStatus.choices):
        raise HTTPException(status_code=422, detail="invalid_status")
    booking = await Booking.objects.acreate(
        property=prop,
        renter=renter,
        owner=owner,
        status=status,
        monthly_rent=Decimal(
            str(body_float(data, "monthly_rent", float(prop.price_per_month)))
        ),
        lease_months=body_int(data, "lease_months", 12) or 12,
        move_in_date=_parse_date(body_str(data, "move_in_date")),
        note=body_str(data, "note"),
    )
    await audit(
        actor,
        AuditLog.Action.CREATE,
        "booking",
        booking.pk,
        f"created {booking.reference}",
    )
    return {"booking": await serialize_booking(booking)}


@console_api.post("/bookings/{pk}/edit/")
async def booking_edit(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    booking = await Booking.objects.filter(pk=pk).afirst()
    if booking is None:
        raise _not_found("booking")
    data = json_body(request)
    if "status" in data:
        status = body_str(data, "status")
        if status not in dict(BookingStatus.choices):
            raise HTTPException(status_code=422, detail="invalid_status")
        booking.status = status
    if "monthly_rent" in data:
        booking.monthly_rent = Decimal(str(body_float(data, "monthly_rent", 0)))
    if "lease_months" in data:
        booking.lease_months = body_int(data, "lease_months", booking.lease_months) or 1
    if "move_in_date" in data:
        booking.move_in_date = _parse_date(body_str(data, "move_in_date"))
    if "note" in data:
        booking.note = body_str(data, "note")
    await booking.asave()
    await audit(
        actor,
        AuditLog.Action.UPDATE,
        "booking",
        booking.pk,
        f"updated {booking.reference}",
    )
    return {"booking": await serialize_booking(booking)}


@console_api.post("/bookings/{pk}/delete/")
async def booking_delete(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    booking = await Booking.objects.filter(pk=pk).afirst()
    if booking is None:
        raise _not_found("booking")
    ref = booking.reference
    await booking.adelete()
    await audit(actor, AuditLog.Action.DELETE, "booking", pk, f"deleted {ref}")
    return {"ok": True, "deleted": pk}


@console_api.post("/bookings/bulk-delete/")
async def bookings_bulk_delete(request):
    actor = await superadmin_required(request)
    ids = _ids(json_body(request))
    await Booking.objects.filter(pk__in=ids).adelete()
    await audit(
        actor,
        AuditLog.Action.DELETE,
        "booking",
        ",".join(map(str, ids)),
        "bulk deleted bookings",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Payments & refunds
# ---------------------------------------------------------------------------


@console_api.get("/payments/")
async def payments_list(request):
    await superadmin_required(request)
    from core.bolt import q

    query = q(request, "q")
    status = q(request, "status", "all")
    queryset = Payment.objects.select_related(
        "property", "property__owner", "user", "booking"
    ).order_by("-created_at")
    if query:
        queryset = queryset.filter(
            Q(reference__icontains=query)
            | Q(property__title__icontains=query)
            | Q(user__email__icontains=query)
        )
    if status in Payment.Status.values:
        queryset = queryset.filter(status=status)
    elif status == "Refunded":
        queryset = queryset.filter(refund_status=Payment.RefundStatus.PROCESSED)

    status_counts = {"all": await Payment.objects.acount()}
    async for row in Payment.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    status_counts["Refunded"] = await Payment.objects.filter(
        refund_status=Payment.RefundStatus.PROCESSED
    ).acount()

    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "refunds": [
            await serialize_refund(r)
            async for r in Refund.objects.select_related(
                "payment",
                "booking",
                "payment__property",
                "payment__property__owner",
                "payment__user",
            )[:10]
        ],
        "query": query,
        "status": status,
        "status_counts": status_counts,
        "total": await Payment.objects.acount(),
        "revenue": float(
            (
                await Payment.objects.filter(
                    status=Payment.Status.SUCCESS
                ).aaggregate(v=Sum("amount"))
            )["v"]
            or 0
        ),
    }


@console_api.post("/payments/new/")
async def payment_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    user = await User.objects.filter(pk=_optional_id(data, "user")).afirst()
    booking = await Booking.objects.filter(pk=_optional_id(data, "booking")).afirst()
    prop = await Property.objects.filter(pk=_optional_id(data, "property")).afirst()
    if prop is None and booking is not None and booking.property_id:
        prop = await Property.objects.filter(pk=booking.property_id).afirst()
    amount = body_float(data, "amount")
    if amount is None:
        if booking is not None:
            amount = float(booking.monthly_rent)
        elif prop is not None:
            amount = float(prop.price_per_month)
    if user is None or amount is None:
        raise HTTPException(status_code=422, detail="user_and_amount_required")

    payment = await Payment.objects.acreate(
        property=prop,
        user=user,
        booking=booking,
        amount=Decimal(str(amount)),
        method=body_str(data, "method") or Payment.Method.ABA,
        status=body_str(data, "status") or Payment.Status.SUCCESS,
    )
    await audit(
        actor,
        AuditLog.Action.CREATE,
        "payment",
        payment.pk,
        f"created {payment.reference}",
    )
    return {"payment": await serialize_payment(payment)}


@console_api.post("/payments/{pk}/edit/")
async def payment_edit(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    payment = await Payment.objects.filter(pk=pk).afirst()
    if payment is None:
        raise _not_found("payment")
    data = json_body(request)
    if "amount" in data:
        payment.amount = Decimal(str(body_float(data, "amount", float(payment.amount))))
    if "method" in data:
        payment.method = body_str(data, "method") or payment.method
    if "status" in data:
        payment.status = body_str(data, "status") or payment.status
    if "refund_status" in data:
        payment.refund_status = body_str(data, "refund_status") or payment.refund_status
    if "refunded_amount" in data:
        payment.refunded_amount = Decimal(
            str(body_float(data, "refunded_amount", float(payment.refunded_amount)))
        )
    await payment.asave()
    await audit(
        actor,
        AuditLog.Action.UPDATE,
        "payment",
        payment.pk,
        f"updated {payment.reference}",
    )
    return {"payment": await serialize_payment(payment)}


@console_api.post("/payments/{pk}/delete/")
async def payment_delete(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    payment = await Payment.objects.filter(pk=pk).afirst()
    if payment is None:
        raise _not_found("payment")
    ref = payment.reference
    await payment.adelete()
    await audit(actor, AuditLog.Action.DELETE, "payment", pk, f"deleted {ref}")
    return {"ok": True, "deleted": pk}


@console_api.post("/payments/bulk-delete/")
async def payments_bulk_delete(request):
    actor = await superadmin_required(request)
    ids = _ids(json_body(request))
    await Payment.objects.filter(pk__in=ids).adelete()
    await audit(
        actor,
        AuditLog.Action.DELETE,
        "payment",
        ",".join(map(str, ids)),
        "bulk deleted payments",
    )
    return {"ok": True}


@console_api.post("/refunds/{pk}/process/")
async def refund_process(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    refund = await Refund.objects.filter(pk=pk).afirst()
    if refund is None:
        raise _not_found("refund")
    ok = await in_thread(process_refund, refund, actor=actor)
    await audit(actor, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    if not ok:
        raise HTTPException(status_code=409, detail="refund_already_processed")
    return {"ok": True, "refund": await serialize_refund(refund)}


@console_api.post("/refunds/new/")
async def refund_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    payment = await Payment.objects.filter(pk=_optional_id(data, "payment")).afirst()
    if payment is None:
        raise HTTPException(status_code=422, detail="payment_required")
    booking = None
    if payment.booking_id:
        booking = await Booking.objects.filter(pk=payment.booking_id).afirst()
    if booking is None:
        booking = await Booking.objects.filter(payment=payment).afirst()
    if booking is None:
        raise HTTPException(status_code=422, detail="booking_required")
    refund = await Refund.objects.acreate(
        payment=payment,
        booking=booking,
        amount=payment.amount,
        reason=body_str(data, "reason") or Refund.Reason.OTHER,
    )
    await audit(actor, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    return {"refund": await serialize_refund(refund)}


mark_full_request(console_api)

__all__ = ["console_api"]