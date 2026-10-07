"""Core JSON endpoints: landing, health and session preferences."""

from __future__ import annotations

from django.db.models import Avg, Sum
from django_bolt import BoltAPI
from django_bolt.responses import Redirect

from core.bolt import (
    get_user,
    login_required,
    mark_full_request,
    session_set,
)
from core.bolt_serializers import property as serialize_property

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


async def _landing_payload(limit: int = 6) -> dict:
    from bookings.models import Booking, BookingStatus
    from listings.models import Property
    from payments.models import Payment

    properties = Property.objects.select_related("owner").order_by("-created_at")
    stats = {
        "properties": await properties.acount(),
        "owners": await properties.values("owner_id").distinct().acount(),
        "bookings": await Booking.objects.acount(),
        "cities": await properties.values("location").distinct().acount(),
        "avg_price": float(
            (await Property.objects.aaggregate(v=Avg("price_per_month")))["v"] or 0
        ),
        "revenue": float(
            (
                await Payment.objects.filter(status=Payment.Status.SUCCESS).aaggregate(
                    v=Sum("amount")
                )
            )["v"]
            or 0
        ),
    }
    return {
        "stats": stats,
        "featured": [await serialize_property(p) async for p in properties[:limit]],
        "has_data": await properties.aexists() and await Booking.objects.aexists(),
        "pending_bookings": await Booking.objects.filter(
            status=BookingStatus.PENDING
        ).acount(),
    }


@api.get("/")
async def home(request):
    user = await get_user(request)
    if user is not None:
        return Redirect(user.home_url)
    return await _landing_payload()


@api.get("/core/landing/")
async def landing(request):
    return await _landing_payload()


@api.get("/core/health/")
async def health(request):
    from accounts.models import User
    from bookings.models import Booking, BookingStatus
    from listings.models import Property
    from payments.models import Payment

    return {
        "status": "ok",
        "users": await User.objects.acount(),
        "properties": await Property.objects.acount(),
        "bookings": await Booking.objects.acount(),
        "payments": await Payment.objects.acount(),
        "bookings_pending": await Booking.objects.filter(
            status=BookingStatus.PENDING
        ).acount(),
    }


@api.post("/core/tour/")
async def dismiss_tour(request):
    await login_required(request)
    await session_set(request, "renteasy_seen_tour", True)
    return {"ok": True, "seen_tour": True}


mark_full_request(api)

__all__ = ["api"]
