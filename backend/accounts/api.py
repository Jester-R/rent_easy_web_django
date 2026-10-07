"""Accounts JSON endpoints: auth, profile, rener/owner dashboards, and the
superadmin console (mounted from :mod:`accounts.console_api`).

Handlers are native async Django-Bolt handlers: ORM reads use the Django async
ORM and ``django.contrib.auth`` / manager / model helpers hop to a worker
thread via :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Q, Sum
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from accounts.models import (
    AuditLog,
    Role,
    User,
    is_valid_username,
    normalize_identity,
)
from bookings.models import Booking, BookingStatus
from core.bolt import (
    body_str,
    in_thread,
    json_body,
    mark_full_request,
    owner_required,
    q,
    renter_required,
    session_get,
    session_pop,
    session_set,
)
from core.bolt import login_required as require_login
from core.bolt_serializers import booking as serialize_booking
from core.bolt_serializers import payment as serialize_payment
from core.bolt_serializers import property as serialize_property
from core.bolt_serializers import user as serialize_user
from listings.models import Favorite, Property
from payments.models import Payment

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)

PENDING_ROLE_KEY = "renteasy_pending_role_user"
FLASH_KEY = "renteasy_flash"


async def _flash(request, key: str) -> None:
    await session_set(request, FLASH_KEY, key)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@api.get("/auth/login/")
async def login_state(request):
    from core.bolt import get_user

    user = await get_user(request)
    if user is not None:
        return {"authenticated": True, "user": await serialize_user(user)}
    return {"authenticated": False}


@api.post("/auth/login/")
async def login_view(request):
    data = json_body(request)
    identifier = normalize_identity(
        body_str(data, "identifier") or body_str(data, "email")
    )
    password = body_str(data, "password")
    if not identifier or not password:
        raise HTTPException(status_code=422, detail="credentials_required")

    user = await in_thread(
        authenticate, request, username=identifier, password=password
    )
    if user is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="not_authorized")

    await in_thread(login, request, user)
    await in_thread(user.touch_login)

    destination = body_str(data, "next") or user.home_url
    if not destination.startswith("/"):
        destination = user.home_url
    return {
        "user": await serialize_user(user),
        "home_url": user.home_url,
        "redirect": destination,
    }


@api.post("/auth/register/")
async def register_view(request):
    data = json_body(request)
    full_name = body_str(data, "full_name")
    username = body_str(data, "username")
    email = normalize_identity(body_str(data, "email"))
    password = body_str(data, "password")
    confirm = body_str(data, "password_confirm")

    if not email:
        raise HTTPException(status_code=422, detail="email_required")
    if not password:
        raise HTTPException(status_code=422, detail="password_required")
    if password != confirm:
        raise HTTPException(status_code=422, detail="password_mismatch")
    if not is_valid_username(username):
        raise HTTPException(status_code=422, detail="username_invalid")
    if await User.objects.filter(email__iexact=email).aexists():
        raise HTTPException(status_code=409, detail="email_taken")
    if await User.objects.filter(username__iexact=username).aexists():
        raise HTTPException(status_code=409, detail="username_taken")

    user = await in_thread(
        User.objects.create_user,
        email=email,
        username=username,
        password=password,
        full_name=full_name,
        role=Role.RENTER,
    )
    await session_set(request, PENDING_ROLE_KEY, str(user.pk))
    return {"user_id": user.pk, "redirect": "/role/"}


@api.post("/auth/role/")
async def role_select_view(request):
    data = json_body(request)
    pending_id = await session_get(request, PENDING_ROLE_KEY)
    if not pending_id:
        raise HTTPException(status_code=409, detail="no_pending_registration")

    user = await User.objects.filter(pk=pending_id).afirst()
    if user is None:
        await session_pop(request, PENDING_ROLE_KEY, None)
        raise HTTPException(status_code=404, detail="pending_user_missing")

    role = body_str(data, "role")
    if role not in {Role.RENTER, Role.OWNER}:
        raise HTTPException(status_code=422, detail="select_role_hint")

    user.role = role
    await user.asave(update_fields=["role"])
    await AuditLog.objects.acreate(
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity="user",
        entity_id=str(user.pk),
        summary=f"role set to {user.role}",
    )
    await session_pop(request, PENDING_ROLE_KEY, None)
    await _flash(request, "registration_complete")
    return {"ok": True, "role": role, "home_url": user.home_url, "redirect": "/login/"}


@api.post("/auth/logout/")
async def logout_view(request):
    from core.bolt import get_user

    user = await get_user(request)
    await AuditLog.objects.acreate(
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity="session",
        entity_id=str(user.pk) if user else "",
        summary="logout",
    )
    await in_thread(logout, request)
    return {"ok": True, "redirect": "/login/"}


# ---------------------------------------------------------------------------
# Profile + preferences
# ---------------------------------------------------------------------------


@api.get("/auth/preferences/")
async def profile_get(request):
    user = await require_login(request)
    return {"user": await serialize_user(user)}


@api.post("/auth/preferences/")
async def profile_update(request):
    user = await require_login(request)
    data = json_body(request)

    full_name = body_str(data, "full_name")
    username = body_str(data, "username")
    email = normalize_identity(body_str(data, "email"))

    if email and await User.objects.filter(email__iexact=email).exclude(
        pk=user.pk
    ).aexists():
        raise HTTPException(status_code=409, detail="email_taken")
    if username:
        if not is_valid_username(username):
            raise HTTPException(status_code=422, detail="username_invalid")
        if await User.objects.filter(username__iexact=username).exclude(
            pk=user.pk
        ).aexists():
            raise HTTPException(status_code=409, detail="username_taken")

    if "full_name" in data:
        user.full_name = full_name
    if email:
        user.email = email
    if username:
        user.username = username
    await user.asave()
    await _flash(request, "account_updated")
    return {"user": await serialize_user(user)}


@api.get("/auth/denied/")
async def deny(request):
    raise HTTPException(
        status_code=403,
        detail=f"role_required:{q(request, 'role') or 'unknown'}",
    )


@api.post("/i18n/set/")
async def set_language_view(request):
    from core.i18n import SUPPORTED_LANGUAGE_CODES

    data = json_body(request)
    code = (body_str(data, "lang") or q(request, "lang")).strip()[:2]
    if code not in SUPPORTED_LANGUAGE_CODES:
        raise HTTPException(status_code=422, detail="unsupported_language")
    await session_set(request, "renteasy_language", code)
    return {"ok": True, "language": code}


@api.post("/theme/set/")
async def set_theme_view(request):
    from core.middleware import THEMES

    data = json_body(request)
    theme = (body_str(data, "theme") or q(request, "theme")).strip().lower()
    if theme not in THEMES:
        raise HTTPException(status_code=422, detail="unsupported_theme")
    await session_set(request, "renteasy_theme", theme)
    return {"ok": True, "theme": theme}


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------


@api.get("/rent/")
async def renter_dashboard(request):
    user = await renter_required(request)
    properties = Property.objects.filter(owner__role=Role.OWNER).order_by("-created_at")
    bookings = (
        Booking.objects.filter(renter=user)
        .select_related("property", "owner", "payment")
        .order_by("-created_at")
    )
    payments = Payment.objects.select_related("property", "booking", "user").filter(
        user=user
    ).order_by("-created_at")
    favorites = Favorite.objects.filter(user=user).select_related("property")

    counts = {
        row["status"]: row["n"]
        async for row in bookings.values("status").annotate(n=Count("id"))
    }
    spend = (
        await payments.filter(status=Payment.Status.SUCCESS).aaggregate(
            v=Sum("amount")
        )
    )["v"] or 0
    refunded = (await payments.aaggregate(v=Sum("refunded_amount")))["v"] or 0

    blocked = Booking.objects.filter(
        renter=user, status__in=[BookingStatus.PENDING, BookingStatus.APPROVED]
    ).values_list("property_id", flat=True)
    suggested = properties.exclude(id__in=blocked)[:6]
    favorite_ids = {
        v async for v in favorites.values_list("property_id", flat=True)
    }

    return {
        "stats": {
            "available": await Property.objects.filter(
                owner__role=Role.OWNER
            ).acount(),
            "bookings": await bookings.acount(),
            "active": counts.get(BookingStatus.PENDING, 0)
            + counts.get(BookingStatus.APPROVED, 0),
            "pending": counts.get(BookingStatus.PENDING, 0),
            "approved": counts.get(BookingStatus.APPROVED, 0),
            "favorites": await favorites.acount(),
            "payments": await payments.acount(),
            "spend": float(spend),
            "refunded": float(refunded),
        },
        "featured": [await serialize_property(p) async for p in properties[:3]],
        "suggested": [
            await serialize_property(p, is_favorite=p.pk in favorite_ids)
            async for p in suggested
        ],
        "recent_bookings": [await serialize_booking(b) async for b in bookings[:5]],
        "recent_payments": [await serialize_payment(p) async for p in payments[:5]],
        "favorite_ids": sorted(favorite_ids),
    }


@api.get("/owner/")
async def owner_dashboard(request):
    user = await owner_required(request)
    properties = (
        Property.objects.filter(owner=user)
        .select_related("owner")
        .annotate(
            favorite_count=Count("favorites", distinct=True),
            booking_count=Count("bookings", distinct=True),
            revenue=Sum(
                "payments__amount", filter=Q(payments__status=Payment.Status.SUCCESS)
            ),
        )
        .order_by("-created_at")
    )
    bookings = (
        Booking.objects.filter(owner=user)
        .select_related("property", "renter", "payment")
        .order_by("-created_at")
    )
    payments = Payment.objects.select_related("property", "booking", "user").filter(
        property__owner=user
    ).order_by("-created_at")

    counts = {
        row["status"]: row["n"]
        async for row in bookings.values("status").annotate(n=Count("id"))
    }
    potential = (await properties.aaggregate(v=Sum("price_per_month")))["v"] or 0
    revenue = (
        await payments.filter(status=Payment.Status.SUCCESS).aaggregate(
            v=Sum("amount")
        )
    )["v"] or 0
    favorites = await Favorite.objects.filter(property__owner=user).acount()

    return {
        "stats": {
            "listings": await properties.acount(),
            "pending": counts.get(BookingStatus.PENDING, 0),
            "approved": counts.get(BookingStatus.APPROVED, 0),
            "rejected": counts.get(BookingStatus.REJECTED, 0),
            "cancelled": counts.get(BookingStatus.CANCELLED, 0),
            "potential": float(potential),
            "revenue": float(revenue),
            "favorites": favorites,
            "bookings": await bookings.acount(),
            "payments": await payments.acount(),
        },
        "properties": [await serialize_property(p) async for p in properties],
        "recent_bookings": [await serialize_booking(b) async for b in bookings[:5]],
        "recent_payments": [await serialize_payment(p) async for p in payments[:5]],
    }


from accounts.console_api import console_api

api.mount("/console", console_api)


mark_full_request(api)

__all__ = ["api"]
