"""Core JSON endpoints: landing, health and session preferences."""

from __future__ import annotations

import logging
import mimetypes
import os

import httpx
from django.conf import settings
from django.db.models import Avg, Sum
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException
from django_bolt.responses import FileResponse, Redirect

from core.ai import (
    AIConfigError,
    generate_property_description,
    generate_property_draft,
)
from core.bolt import (
    body_float,
    body_int,
    body_str,
    get_user,
    json_body,
    login_required,
    mark_full_request,
    owner_required,
    session_set,
)
from core.bolt_serializers import property as serialize_property
from core.maps import resolve_google_maps_url

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)
logger = logging.getLogger(__name__)


async def _landing_payload(request, limit: int = 6) -> dict:
    from accounts.default_promotion import DEFAULT_HOME_PROMOTION
    from accounts.models import PlatformSettings
    from bookings.models import Booking, BookingStatus
    from listings.models import Favorite, Property
    from payments.models import Payment

    confirmed_property_ids = Booking.objects.filter(
        status=BookingStatus.CONFIRMED
    ).values_list("property_id", flat=True)
    properties = (
        Property.objects.select_related("owner")
        .exclude(pk__in=confirmed_property_ids)
        .order_by("-created_at")
    )
    featured_properties = [p async for p in properties[:limit]]
    user = await get_user(request)
    favorite_ids = set()
    if user is not None and user.is_renter:
        favorite_ids = {
            property_id
            async for property_id in Favorite.objects.filter(
                user=user, property_id__in=[p.pk for p in featured_properties]
            ).values_list("property_id", flat=True)
        }
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
    stored_promotion = (
        await PlatformSettings.objects.filter(pk=1)
        .values_list("home_promotion", flat=True)
        .afirst()
    )
    promotion = {**DEFAULT_HOME_PROMOTION, **(stored_promotion or {})}
    return {
        "home_promotion": promotion,
        "stats": stats,
        "featured": [
            await serialize_property(p, is_favorite=p.pk in favorite_ids)
            for p in featured_properties
        ],
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
    return await _landing_payload(request)


@api.get("/core/landing/")
async def landing(request):
    return await _landing_payload(request)


@api.get("/core/payment-method-details/")
async def payment_method_details(request):
    from accounts.models import PlatformSettings
    from payments.models import Payment

    raw = (
        await PlatformSettings.objects.filter(pk=1)
        .values_list("payment_method_details", flat=True)
        .afirst()
    )
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for method in (Payment.Method.ABA, Payment.Method.STRIPE):
        item = raw.get(method) or {}
        if not isinstance(item, dict):
            item = {}
        result[method] = {
            key: str(item.get(key, "") or "")[:255]
            for key in (
                "account_name",
                "account_number",
                "instructions_en",
                "instructions_km",
            )
        }
    return {"payment_method_details": result}


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


@api.post("/ai/property-description/")
async def ai_property_description(request):
    await owner_required(request)
    data = json_body(request)

    if body_str(data, "prompt"):
        details = {
            "prompt": body_str(data, "prompt"),
            "locations": data.get("locations", []),
            "categories": data.get("categories", []),
        }
        try:
            return await generate_property_draft(details)
        except AIConfigError as exc:
            raise HTTPException(status_code=503, detail="ai_not_configured") from exc
        except Exception as exc:
            logger.exception("AI property draft generation failed")
            raise HTTPException(status_code=502, detail="ai_generation_failed") from exc

    details = {
        "title": body_str(data, "title"),
        "title_km": body_str(data, "title_km"),
        "location": body_str(data, "location"),
        "category": body_str(data, "category"),
        "price_per_month": body_float(data, "price_per_month"),
        "bedrooms": body_int(data, "bedrooms", 0),
        "bathrooms": body_int(data, "bathrooms", 0),
        "notes": body_str(data, "notes"),
    }

    if not details["title"] and not details["title_km"]:
        raise HTTPException(status_code=422, detail="title_required")

    try:
        return await generate_property_description(details)
    except AIConfigError as exc:
        raise HTTPException(status_code=503, detail="ai_not_configured") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="ai_generation_failed") from exc


@api.post("/maps/resolve/")
async def resolve_maps_link(request):
    await owner_required(request)
    data = json_body(request)
    try:
        coordinates = await resolve_google_maps_url(body_str(data, "url"))
    except httpx.HTTPError as exc:
        logger.info("Google Maps link lookup failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="maps_link_unavailable") from exc
    if coordinates is None:
        raise HTTPException(status_code=422, detail="coordinates_not_found")
    return {"latitude": coordinates[0], "longitude": coordinates[1]}


@api.get("/media/{path:path}")
async def serve_media(path: str):
    """Serve uploaded media files from MEDIA_ROOT."""
    media_root = str(settings.MEDIA_ROOT or "")
    if not media_root:
        raise HTTPException(status_code=404, detail="media_not_configured")
    # Prevent path traversal
    abs_path = os.path.realpath(os.path.join(media_root, path))
    if not abs_path.startswith(os.path.realpath(media_root)):
        raise HTTPException(status_code=404, detail="not_found")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="not_found")
    mime_type, _ = mimetypes.guess_type(abs_path)
    return FileResponse(abs_path, media_type=mime_type)


mark_full_request(api)

__all__ = ["api"]
