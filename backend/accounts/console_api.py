"""Superadmin console JSON endpoints (mounted under ``/console``).

This module intentionally defines its own :class:`BoltAPI` named
``console_api`` (not ``api``) so django-bolt's auto-discovery does not pick it
up as a standalone app API; it is mounted by :mod:`accounts.api`.

Handlers are native async Django-Bolt handlers; the synchronous
payment/notification services and manager helpers hop through
:func:`core.bolt.in_thread`.
"""

from __future__ import annotations


from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from accounts.models import (
    ApprovalStatus,
    AuditLog,
    PlatformSettings,
    Role,
    User,
    is_valid_username,
    normalize_identity,
)
from accounts.default_promotion import DEFAULT_HOME_PROMOTION
from accounts.payouts import apply_payout_fields
from bookings.models import Booking
from core.bolt import (
    admin_required,
    body_bool,
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
from core.bolt_serializers import payout as serialize_payout
from core.bolt_serializers import property as serialize_property
from core.bolt_serializers import refund as serialize_refund
from core.bolt_serializers import user as serialize_user
from listings.models import Favorite, Property
from listings.category_config import DEFAULT_PROPERTY_CATEGORIES
from notifications.models import Notification
from notifications.default_messages import DEFAULT_NOTIFICATION_MESSAGES
from notifications.services import notify
from payments.models import Payment, Payout, Refund
from payments.services import (
    PayoutBlocked,
    PayoutDetailsMissing,
    PayoutNotDue,
    RefundRequiresGateway,
    backfill_missing_payouts,
    cancel_payout_for_payment,
    create_payout_for_payment,
    pay_out,
    process_refund,
    release_due_payouts,
    notify_refund_team,
    reject_refund,
)

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
        except TypeError, ValueError:
            continue
    return out


def _optional_id(data: dict, key: str):
    value = data.get(key)
    if value in (None, "", "null"):
        return None
    return body_int(data, key, 0) or None


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

    await in_thread(backfill_missing_payouts)
    await in_thread(release_due_payouts)
    eligible_payouts = await Payout.objects.filter(
        status=Payout.Status.ELIGIBLE
    ).acount()
    eligible_payout_amount = (
        await Payout.objects.filter(status=Payout.Status.ELIGIBLE).aaggregate(
            v=Sum("amount")
        )
    )["v"] or 0

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
    top_properties = (
        Property.objects.select_related("owner")
        .annotate(
            revenue=Sum(
                "payments__amount", filter=Q(payments__status=Payment.Status.SUCCESS)
            ),
            bookings_total=Count("bookings", distinct=True),
            favorites_total=Count("favorites", distinct=True),
        )
        .order_by("-revenue")[:6]
    )

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
            "eligible_payouts": eligible_payouts,
            "eligible_payout_amount": float(eligible_payout_amount),
        },
        "status_counts": status_counts,
        "monthly_rows": monthly_rows,
        "top_properties": [
            await serialize_property(
                p,
                revenue=float(
                    p.revenue if getattr(p, "revenue", None) is not None else 0
                ),
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
            async for b in Booking.objects.select_related(
                "property", "renter", "owner", "payment", "payment__payout"
            ).order_by("-created_at")[:8]
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
# Settings
# ---------------------------------------------------------------------------


@console_api.get("/settings/")
async def settings_get(request):
    await admin_required(request)
    platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)
    return {
        "settings": {
            "auto_approve_owners": platform.auto_approve_owners,
            "property_categories": platform.property_categories
            or DEFAULT_PROPERTY_CATEGORIES,
            "notification_messages": platform.notification_messages
            or DEFAULT_NOTIFICATION_MESSAGES,
            "home_promotion": {
                **DEFAULT_HOME_PROMOTION,
                **(platform.home_promotion or {}),
            },
        }
    }


def _clean_property_categories(raw):
    import re

    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=422, detail="at_least_one_category_required")
    result, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        value = body_str(item, "value").lower()
        label_en = body_str(item, "label_en")
        label_km = body_str(item, "label_km")
        if not re.fullmatch(r"[a-z0-9_-]{1,24}", value) or value in seen:
            raise HTTPException(status_code=422, detail="invalid_or_duplicate_category")
        if not label_en or not label_km:
            raise HTTPException(status_code=422, detail="category_labels_required")
        result.append(
            {"value": value, "label_en": label_en[:80], "label_km": label_km[:80]}
        )
        seen.add(value)
    if not result:
        raise HTTPException(status_code=422, detail="at_least_one_category_required")
    return result


def _clean_notification_messages(raw):
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail="invalid_notification_messages")
    defaults = {item["key"]: item for item in DEFAULT_NOTIFICATION_MESSAGES}
    result = []
    for item in raw:
        if not isinstance(item, dict) or item.get("key") not in defaults:
            continue
        default = defaults[item["key"]]
        cleaned = {
            key: default[key] for key in ("key", "body_key", "label_en", "label_km")
        }
        for field in ("title_en", "title_km", "body_en", "body_km"):
            value = body_str(item, field)
            if not value:
                raise HTTPException(
                    status_code=422, detail="notification_messages_required"
                )
            cleaned[field] = value[:500]
        result.append(cleaned)
    if len(result) != len(defaults):
        raise HTTPException(status_code=422, detail="notification_messages_incomplete")
    return result


def _clean_home_promotion(raw):
    from urllib.parse import urlparse

    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="invalid_home_promotion")
    result = {}
    limits = {
        "eyebrow_en": 100,
        "eyebrow_km": 100,
        "title_en": 180,
        "title_km": 180,
        "body_en": 500,
        "body_km": 500,
    }
    for field, limit in limits.items():
        result[field] = body_str(raw, field, DEFAULT_HOME_PROMOTION[field])[:limit]
    image_url = body_str(raw, "image_url")
    if image_url.startswith("data:"):
        if len(image_url) > 2_800_000 or not image_url.startswith(
            ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,", "data:image/gif;base64,")
        ):
            raise HTTPException(status_code=422, detail="invalid_home_promotion_image")
    elif image_url:
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail="invalid_home_promotion_image_url")
        if len(image_url) > 1000:
            raise HTTPException(status_code=422, detail="invalid_home_promotion_image_url")
    result["image_url"] = image_url
    return result


@console_api.post("/settings/")
async def settings_update(request):
    actor = await admin_required(request)
    data = json_body(request)
    platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)
    if "auto_approve_owners" in data:
        platform.auto_approve_owners = body_bool(
            data, "auto_approve_owners", platform.auto_approve_owners
        )
    if "property_categories" in data:
        platform.property_categories = _clean_property_categories(
            data["property_categories"]
        )
    if "notification_messages" in data:
        platform.notification_messages = _clean_notification_messages(
            data["notification_messages"]
        )
    if "home_promotion" in data:
        platform.home_promotion = _clean_home_promotion(data["home_promotion"])
        # Persist and fetch the JSONField explicitly. Keeping this as a queryset
        # update avoids reporting success based only on the in-memory singleton
        # (which made the editor appear saved while the homepage kept defaults).
        await PlatformSettings.objects.filter(pk=platform.pk).aupdate(
            home_promotion=platform.home_promotion,
            updated_at=timezone.now(),
        )
        platform.home_promotion = await PlatformSettings.objects.filter(
            pk=platform.pk
        ).values_list("home_promotion", flat=True).afirst()
    await platform.asave()
    await audit(
        actor,
        AuditLog.Action.UPDATE,
        "settings",
        platform.pk,
        "updated platform settings",
    )
    return {
        "settings": {
            "auto_approve_owners": platform.auto_approve_owners,
            "property_categories": platform.property_categories
            or DEFAULT_PROPERTY_CATEGORIES,
            "notification_messages": platform.notification_messages
            or DEFAULT_NOTIFICATION_MESSAGES,
            "home_promotion": {
                **DEFAULT_HOME_PROMOTION,
                **(platform.home_promotion or {}),
            },
        }
    }


def _create_broadcast(target, title_en, title_km, body_en, body_km):
    recipients = User.objects.filter(is_active=True)
    if target == "owners":
        recipients = recipients.filter(role=Role.OWNER)
    elif target == "renters":
        recipients = recipients.filter(role=Role.RENTER)
    ids = list(recipients.values_list("pk", flat=True))
    notifications = [
        Notification(
            recipient_id=user_id,
            kind=Notification.Kind.ANNOUNCEMENT,
            title_key="admin_broadcast",
            body_key="admin_broadcast_body",
            params={
                "message_overrides": {
                    "title_en": title_en,
                    "title_km": title_km,
                    "body_en": body_en,
                    "body_km": body_km,
                }
            },
            link="/notifications/",
        )
        for user_id in ids
    ]
    Notification.objects.bulk_create(notifications, batch_size=1000)
    return len(notifications)


# Some production proxies normalize POST paths by dropping the final slash.
# Keep both forms routed to the same handler so broadcast works regardless of
# that normalization.
@console_api.post("/notifications/broadcast")
@console_api.post("/notifications/broadcast/")
async def notification_broadcast(request):
    actor = await admin_required(request)
    data = json_body(request)
    target = body_str(data, "target")
    if target not in {"owners", "renters", "all"}:
        raise HTTPException(status_code=422, detail="invalid_broadcast_target")
    messages = {
        field: body_str(data, field)[:500]
        for field in ("title_en", "title_km", "body_en", "body_km")
    }
    if not all(messages.values()):
        raise HTTPException(status_code=422, detail="all_broadcast_messages_required")
    sent = await in_thread(
        _create_broadcast,
        target,
        messages["title_en"],
        messages["title_km"],
        messages["body_en"],
        messages["body_km"],
    )
    await audit(
        actor,
        AuditLog.Action.CREATE,
        "notification_broadcast",
        target,
        f"sent announcement to {sent} {target}",
    )
    return {"ok": True, "sent": sent}


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@console_api.get("/users/")
async def users_list(request):
    await superadmin_required(request)
    from core.bolt import pagination, q

    query = q(request, "q")
    role = q(request, "role", "all")
    approval = q(request, "approval", "all")
    queryset = User.objects.all().order_by("-date_joined")
    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(username__icontains=query)
        )
    if role in dict(Role.choices):
        queryset = queryset.filter(role=role)
    if approval in dict(ApprovalStatus.choices):
        queryset = queryset.filter(approval_status=approval)
    queryset = queryset.annotate(
        property_count=Count("properties", distinct=True),
        booking_count=Count("renters_bookings", distinct=True),
    )
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]
    return {
        "users": [
            await serialize_user(u)
            | {"property_count": u.property_count, "booking_count": u.booking_count}
            async for u in queryset
        ],
        "query": query,
        "role": role,
        "approval": approval,
        "roles": [{"value": v, "label": label} for v, label in Role.choices],
        "approvals": [
            {"value": v, "label": label} for v, label in ApprovalStatus.choices
        ],
        "pending_count": await User.objects.filter(
            approval_status=ApprovalStatus.PENDING
        ).acount(),
        "total": total,
        "page": page,
        "page_size": page_size,
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
    if user.is_owner:
        apply_payout_fields(user, data)
        await user.asave()
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
        if (
            await User.objects.filter(username__iexact=username)
            .exclude(pk=user.pk)
            .aexists()
        ):
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
    if "approval_status" in data:
        status = body_str(data, "approval_status")
        if status not in dict(ApprovalStatus.choices):
            raise HTTPException(status_code=422, detail="approval_invalid")
        user.approval_status = status
        if status == ApprovalStatus.APPROVED and "is_active" not in data:
            user.is_active = True

    password = body_str(data, "password")
    if password:
        await in_thread(user.set_password, password)
    if user.is_owner:
        apply_payout_fields(user, data)
    await user.asave()
    await audit(actor, AuditLog.Action.UPDATE, "user", user.pk, f"updated {user.email}")
    return {"user": await serialize_user(user)}


def _notify_owner_decision(owner: User, approved: bool) -> None:
    if approved:
        notify(
            owner,
            Notification.Kind.OWNER_APPROVED,
            "notif_owner_approved",
            "notif_owner_approved_body",
            link="/login/",
            action="login",
        )
    else:
        notify(
            owner,
            Notification.Kind.OWNER_REJECTED,
            "notif_owner_rejected",
            "notif_owner_rejected_body",
            link="/login/",
            action="login",
        )


@console_api.post("/users/{pk}/approve/")
async def user_approve(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    user = await User.objects.filter(pk=pk).afirst()
    if user is None:
        raise _not_found("user")
    user.approval_status = ApprovalStatus.APPROVED
    user.is_active = True
    await user.asave(update_fields=["approval_status", "is_active"])
    await in_thread(_notify_owner_decision, user, True)
    await audit(
        actor, AuditLog.Action.UPDATE, "user", user.pk, f"approved owner {user.email}"
    )
    return {"user": await serialize_user(user)}


@console_api.post("/users/{pk}/reject/")
async def user_reject(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    user = await User.objects.filter(pk=pk).afirst()
    if user is None:
        raise _not_found("user")
    user.approval_status = ApprovalStatus.REJECTED
    user.is_active = False
    await user.asave(update_fields=["approval_status", "is_active"])
    await in_thread(_notify_owner_decision, user, False)
    await audit(
        actor, AuditLog.Action.UPDATE, "user", user.pk, f"rejected owner {user.email}"
    )
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
    from core.bolt import pagination, q

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
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]
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
            async for u in User.objects.filter(role=Role.OWNER).order_by("full_name")[
                :100
            ]
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@console_api.post("/properties/{pk}/delete/")
async def property_soft_delete(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    prop = await Property.objects.filter(pk=pk).afirst()
    if prop is None:
        raise _not_found("property")
    if prop.is_active:
        prop.is_active = False
        await prop.asave(update_fields=["is_active", "updated_at"])
        await audit(
            actor, AuditLog.Action.DELETE, "property", pk, f"soft deleted {prop.title}"
        )
    return {"ok": True, "deleted": pk, "is_active": prop.is_active}


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
    from core.bolt import pagination, q

    query = q(request, "q")
    status = q(request, "status", "all")
    queryset = search_bookings(
        apply_status_filter(booking_all_queryset(), status), query
    )
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]

    status_counts = {"all": await Booking.objects.acount()}
    async for row in Booking.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    return {
        "bookings": [await serialize_booking(b) async for b in queryset],
        "query": query,
        "status": status,
        "status_counts": status_counts,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Payments & refunds
# ---------------------------------------------------------------------------


@console_api.get("/payments/")
async def payments_list(request):
    await admin_required(request)
    from core.bolt import pagination, q

    await in_thread(backfill_missing_payouts)
    await in_thread(release_due_payouts)

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
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]

    status_counts = {"all": await Payment.objects.acount()}
    async for row in Payment.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    status_counts["Refunded"] = await Payment.objects.filter(
        refund_status=Payment.RefundStatus.PROCESSED
    ).acount()

    payout_status = q(request, "payout_status", "all")
    payouts_qs = Payout.objects.select_related(
        "owner",
        "payment",
        "payment__property",
        "payment__booking",
        "payment__booking__property",
    ).order_by("-created_at")
    if query:
        payouts_qs = payouts_qs.filter(
            Q(reference__icontains=query)
            | Q(owner__full_name__icontains=query)
            | Q(owner__email__icontains=query)
            | Q(payment__reference__icontains=query)
            | Q(payment__property__title__icontains=query)
        )
    if payout_status in Payout.Status.values:
        payouts_qs = payouts_qs.filter(status=payout_status)
    payout_page, payout_page_size = pagination(
        request, page_key="payout_page", size_key="payout_page_size"
    )
    payouts_total = await payouts_qs.acount()
    payouts_qs = payouts_qs[
        (payout_page - 1) * payout_page_size : payout_page * payout_page_size
    ]
    payout_agg = await Payout.objects.aaggregate(
        scheduled=Sum("amount", filter=Q(status=Payout.Status.SCHEDULED)),
        eligible=Sum("amount", filter=Q(status=Payout.Status.ELIGIBLE)),
        paid=Sum("amount", filter=Q(status=Payout.Status.PAID)),
    )
    payout_counts = {
        "scheduled": await Payout.objects.filter(
            status=Payout.Status.SCHEDULED
        ).acount(),
        "eligible": await Payout.objects.filter(status=Payout.Status.ELIGIBLE).acount(),
        "paid": await Payout.objects.filter(status=Payout.Status.PAID).acount(),
    }
    refund_qs = Refund.objects.select_related(
        "payment",
        "booking",
        "payment__property",
        "payment__property__owner",
        "payment__user",
        "requested_by",
    ).order_by("-created_at", "-pk")
    refund_status = q(request, "refund_status", "all")
    if refund_status in Refund.Status.values:
        refund_qs = refund_qs.filter(status=refund_status)
    if query:
        refund_qs = refund_qs.filter(
            Q(reference__icontains=query)
            | Q(payment__reference__icontains=query)
            | Q(payment__property__title__icontains=query)
            | Q(requested_by__full_name__icontains=query)
            | Q(requested_by__email__icontains=query)
            | Q(request_note__icontains=query)
        )
    refund_total = await refund_qs.acount()
    refund_page, refund_page_size = pagination(
        request, page_key="refund_page", size_key="refund_page_size"
    )
    refund_qs = refund_qs[
        (refund_page - 1) * refund_page_size : refund_page * refund_page_size
    ]

    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "refunds": [await serialize_refund(r) async for r in refund_qs],
        "refunds_total": refund_total,
        "refund_page": refund_page,
        "refund_page_size": refund_page_size,
        "payouts": [await serialize_payout(p) async for p in payouts_qs],
        "payouts_total": payouts_total,
        "payout_page": payout_page,
        "payout_page_size": payout_page_size,
        "payout_status": payout_status,
        "payout_counts": payout_counts,
        "payout_totals": {
            "scheduled": float(payout_agg["scheduled"] or 0),
            "eligible": float(payout_agg["eligible"] or 0),
            "paid": float(payout_agg["paid"] or 0),
        },
        "query": query,
        "status": status,
        "status_counts": status_counts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "revenue": float(
            (
                await Payment.objects.filter(status=Payment.Status.SUCCESS).aaggregate(
                    v=Sum("amount")
                )
            )["v"]
            or 0
        ),
    }


@console_api.post("/payouts/{pk}/pay/")
async def payout_pay(request):
    pk = param_int(request, "pk")
    actor = await superadmin_required(request)
    payout = await Payout.objects.filter(pk=pk).afirst()
    if payout is None:
        raise _not_found("payout")
    data = json_body(request)
    try:
        ok = await in_thread(pay_out, payout, actor=actor, note=body_str(data, "note"))
    except PayoutNotDue as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    except PayoutBlocked as exc:
        # The failed attempt is rolled back; cancel the unpaid row so the list
        # reflects that this payment can no longer be released.
        await Payout.objects.filter(
            pk=payout.pk,
            status__in=[Payout.Status.SCHEDULED, Payout.Status.ELIGIBLE],
        ).aupdate(status=Payout.Status.CANCELLED, updated_at=timezone.now())
        raise HTTPException(status_code=409, detail=exc.code) from exc
    except PayoutDetailsMissing as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if not ok:
        raise HTTPException(status_code=409, detail="payout_already_paid")
    await audit(
        actor, AuditLog.Action.PAYOUT, "payout", payout.pk, f"paid {payout.reference}"
    )
    payout = await (
        Payout.objects.select_related(
            "owner",
            "payment",
            "payment__property",
            "payment__booking",
            "payment__booking__property",
        )
        .filter(pk=pk)
        .afirst()
    )
    return {"ok": True, "payout": await serialize_payout(payout)}


@console_api.post("/refunds/{pk}/process/")
async def refund_process(request):
    pk = param_int(request, "pk")
    actor = await admin_required(request)
    refund = await Refund.objects.filter(pk=pk).afirst()
    if refund is None:
        raise _not_found("refund")
    data = json_body(request)
    try:
        ok = await in_thread(
            process_refund,
            refund,
            actor=actor,
            external=body_bool(data, "external"),
            note=body_str(data, "note"),
        )
    except RefundRequiresGateway as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if not ok:
        raise HTTPException(status_code=409, detail="refund_already_processed")
    await audit(actor, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    refund = await (
        Refund.objects.select_related(
            "payment",
            "payment__property",
            "payment__property__owner",
            "payment__user",
            "booking",
            "requested_by",
        )
        .filter(pk=pk)
        .afirst()
    )
    return {"ok": True, "refund": await serialize_refund(refund)}


@console_api.post("/refunds/{pk}/reject/")
async def refund_reject(request):
    pk = param_int(request, "pk")
    actor = await admin_required(request)
    refund = await Refund.objects.filter(pk=pk).afirst()
    if refund is None:
        raise _not_found("refund")
    data = json_body(request)
    ok = await in_thread(reject_refund, refund, actor=actor, note=body_str(data, "note"))
    if not ok:
        raise HTTPException(status_code=409, detail="refund_not_pending")
    await audit(actor, AuditLog.Action.REFUND, "refund", refund.pk, f"rejected {refund.reference}")
    refund = await (
        Refund.objects.select_related("payment", "booking", "requested_by")
        .filter(pk=pk)
        .afirst()
    )
    return {"ok": True, "refund": await serialize_refund(refund)}


@console_api.post("/refunds/new/")
async def refund_create(request):
    actor = await superadmin_required(request)
    data = json_body(request)
    payment = await Payment.objects.filter(pk=_optional_id(data, "payment")).afirst()
    if payment is None:
        raise HTTPException(status_code=422, detail="payment_required")
    if not payment.is_successful:
        raise HTTPException(status_code=409, detail="payment_not_refundable")
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
        request_note=body_str(data, "request_note") or "Refund created by an administrator for manual review.",
        requested_by=actor,
    )
    if payment.refund_status != Payment.RefundStatus.PROCESSED:
        payment.refund_status = Payment.RefundStatus.PENDING
        await payment.asave(update_fields=["refund_status"])
    await in_thread(cancel_payout_for_payment, payment)
    await in_thread(notify_refund_team, refund)
    await audit(actor, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    return {"refund": await serialize_refund(refund)}


mark_full_request(console_api)

__all__ = ["console_api"]
