"""Listings JSON endpoints: renter browse/favorites, owner CRUD, public detail.

Handlers are native async Django-Bolt handlers; only the payment service
(``create_booking``) hops through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Max, Min, Q
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from core.bolt import (
    body_float,
    body_int,
    body_str,
    get_user,
    in_thread,
    json_body,
    mark_full_request,
    owner_required,
    param_int,
    q,
    renter_required,
)
from core.bolt_serializers import property as serialize_property
from listings.models import Favorite, Property, PropertyCategory

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)

ALL_LOCATIONS = "__all__"
ALL_CATEGORIES = "__all__"
MAX_PRICE_CEILING = Decimal(5000)
MIN_PRICE_FLOOR = Decimal(300)


def _category_options() -> list[dict]:
    return [
        {"value": value, "label": label} for value, label in PropertyCategory.choices
    ]


def _counts(queryset):
    return queryset.annotate(
        favorite_count=Count("favorites", distinct=True),
        booking_count=Count("bookings", distinct=True),
    )


async def _get_property(pk: int) -> Property:
    prop = await Property.objects.select_related("owner").filter(pk=pk, is_active=True).afirst()
    if prop is None:
        raise HTTPException(status_code=404, detail="property_not_found")
    return prop


async def _owned_property(pk: int, user) -> Property:
    prop = await Property.objects.filter(pk=pk, owner=user).afirst()
    if prop is None:
        raise HTTPException(status_code=404, detail="property_not_found")
    return prop


CATEGORY_VALUES = {value for value, _ in PropertyCategory.choices}
MAX_IMAGES = 12


def _clean_images(data: dict) -> list[str]:
    raw = data.get("images")
    if isinstance(raw, str):
        raw = [line.strip() for line in raw.splitlines()]
    if not isinstance(raw, list):
        return []
    images = []
    for item in raw:
        if not isinstance(item, str):
            continue
        url = item.strip()
        if url and url not in images:
            images.append(url)
        if len(images) >= MAX_IMAGES:
            break
    return images


def _clean_coordinate(value, limit: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < -limit or number > limit:
        return None
    return number


def _validate_property_payload(data: dict) -> dict:
    title = body_str(data, "title")
    location = body_str(data, "location")
    price = body_float(data, "price_per_month", 0)
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    if not location:
        raise HTTPException(status_code=422, detail="location_required")
    if price is None or price <= 0:
        raise HTTPException(status_code=422, detail="price_required")

    category = body_str(data, "category")
    if category and category not in CATEGORY_VALUES:
        category = ""

    latitude = _clean_coordinate(data.get("latitude"), 90)
    longitude = _clean_coordinate(data.get("longitude"), 180)
    if (latitude is None) != (longitude is None):
        latitude = longitude = None

    return {
        "title": title,
        "location": location,
        "price_per_month": Decimal(str(price)),
        "bedrooms": max(0, body_int(data, "bedrooms", 0)),
        "bathrooms": max(0, body_int(data, "bathrooms", 0)),
        "description": body_str(data, "description"),
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "images": _clean_images(data),
    }


# ---------------------------------------------------------------------------
# Renter
# ---------------------------------------------------------------------------


@api.get("/rent/properties/")
async def renter_browse(request):
    from accounts.models import Role
    from bookings.models import Booking, BookingStatus

    user = await get_user(request)
    renter = user if user is not None and user.is_renter else None

    # Browse cards need the owner fields, but not aggregate favorite/booking
    # counts. Avoid joining both reverse relations on every public search.
    queryset = (
        Property.objects.select_related("owner")
        .filter(owner__role=Role.OWNER)
        .for_renter(renter)
    )

    search = q(request, "q")
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(location__icontains=search)
            | Q(description__icontains=search)
        )

    location = q(request, "location")
    if location and location != ALL_LOCATIONS:
        queryset = queryset.filter(location__iexact=location)

    category = q(request, "category")
    if category and category != ALL_CATEGORIES:
        queryset = queryset.filter(category=category)

    min_bedrooms = int(q(request, "min_bedrooms") or 0)
    if min_bedrooms:
        queryset = queryset.filter(bedrooms__gte=min_bedrooms)

    raw_max = q(request, "max_price")
    if raw_max:
        with contextlib.suppress(InvalidOperation, ValueError):
            queryset = queryset.filter(price_per_month__lte=Decimal(raw_max))

    sort = q(request, "sort", "recommended")
    if sort == "price_low":
        queryset = queryset.order_by("price_per_month", "title")
    elif sort == "price_high":
        queryset = queryset.order_by("-price_per_month", "title")
    elif sort == "bedrooms":
        queryset = queryset.order_by("-bedrooms", "price_per_month")
    else:
        queryset = queryset.order_by("-created_at", "title")

    properties = [p async for p in queryset]
    ids = [p.pk for p in properties]
    favorite_ids = set()
    active_ids = set()
    if renter is not None:
        favorite_ids = {
            v
            async for v in Favorite.objects.filter(user=renter, property_id__in=ids)
            .values_list("property_id", flat=True)
        }
        active_ids = {
            v
            async for v in Booking.objects.filter(
                renter=renter,
                property_id__in=ids,
                status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
            ).values_list("property_id", flat=True)
        }

    bounds = await Property.objects.aaggregate(
        lo=Min("price_per_month"), hi=Max("price_per_month")
    )
    avg_price = (
        sum(float(p.price_per_month) for p in properties) / len(properties)
        if properties
        else 0.0
    )

    return {
        "properties": [
            await serialize_property(
                p,
                is_favorite=p.pk in favorite_ids,
                has_active_booking=p.pk in active_ids,
            )
            for p in properties
        ],
        "meta": {
            "locations": [
                loc
                async for loc in Property.objects.exclude(location="")
                .order_by("location")
                .values_list("location", flat=True)
                .distinct()
            ],
            "avg_price": avg_price,
            "price_floor": float(bounds["lo"] or MIN_PRICE_FLOOR),
            "price_ceiling": float(bounds["hi"] or MAX_PRICE_CEILING),
            "all_locations_token": ALL_LOCATIONS,
            "categories": _category_options(),
            "all_categories_token": ALL_CATEGORIES,
        },
        "filters": {
            "q": search,
            "location": location,
            "category": category,
            "min_bedrooms": min_bedrooms,
            "max_price": raw_max,
            "sort": sort,
        },
    }


@api.get("/rent/property/{pk}/")
async def renter_detail(request):
    pk = param_int(request, "pk")
    from bookings.models import Booking, BookingStatus

    user = await renter_required(request)
    prop = await _get_property(pk)
    if await Booking.objects.filter(
        property=prop, status=BookingStatus.CONFIRMED
    ).aexists():
        raise HTTPException(status_code=404, detail="property_not_found")
    is_favorite = await Favorite.objects.filter(user=user, property=prop).aexists()
    active_booking = await (
        Booking.objects.filter(
            renter=user,
            property=prop,
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        )
        .order_by("-created_at")
        .afirst()
    )
    approved_count = await Booking.objects.filter(
        property=prop, status=BookingStatus.APPROVED
    ).acount()
    return {
        "property": await serialize_property(
            prop,
            is_favorite=is_favorite,
            approved_bookings=approved_count,
        ),
        "active_booking_id": active_booking.pk if active_booking else None,
    }


@api.get("/rent/favorites/")
async def renter_favorites(request):
    user = await renter_required(request)
    favorite_ids = set(
        {
            v
            async for v in Favorite.objects.filter(user=user).values_list(
                "property_id", flat=True
            )
        }
    )
    favorites = _counts(
        Property.objects.filter(pk__in=favorite_ids)
        .select_related("owner")
        .for_renter(user)
    ).order_by("-created_at")
    return {
        "favorites": [
            await serialize_property(p, is_favorite=True) async for p in favorites
        ],
        "count": len(favorite_ids),
    }


@api.post("/rent/property/{pk}/favorite/")
async def toggle_favorite(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    prop = await _get_property(pk)
    favorite, created = await Favorite.objects.aget_or_create(user=user, property=prop)
    if not created:
        await favorite.adelete()
    return {
        "favorited": created,
        "count": await Favorite.objects.filter(property=prop).acount(),
    }


@api.post("/rent/property/{pk}/request/")
async def booking_request(request):
    pk = param_int(request, "pk")
    from payments.services import create_booking

    user = await renter_required(request)
    prop = await _get_property(pk)
    data = json_body(request)

    booking = await in_thread(
        create_booking,
        property_obj=prop,
        renter=user,
        move_in_date=body_str(data, "move_in_date") or None,
        end_date=body_str(data, "end_date") or None,
        lease_months=body_int(data, "lease_months", 12) or 12,
        note=body_str(data, "note"),
    )
    if booking is None:
        raise HTTPException(status_code=409, detail="active_booking_exists")
    return {"booking_id": booking.pk, "reference": booking.reference}


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------


@api.get("/owner/properties/")
async def owner_list(request):
    user = await owner_required(request)
    properties = _counts(Property.objects.filter(owner=user)).order_by("-created_at")
    return {"properties": [await serialize_property(p) async for p in properties]}


@api.post("/owner/properties/new/")
async def owner_create(request):
    user = await owner_required(request)
    data = _validate_property_payload(json_body(request))
    prop = await Property.objects.acreate(owner=user, **data)
    return {"property": await serialize_property(prop)}


@api.post("/owner/properties/{pk}/edit/")
async def owner_edit(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    prop = await _owned_property(pk, user)
    data = _validate_property_payload(json_body(request))
    for field, value in data.items():
        setattr(prop, field, value)
    await prop.asave()
    return {"property": await serialize_property(prop)}


@api.post("/owner/properties/{pk}/delete/")
async def owner_delete(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    prop = await _owned_property(pk, user)
    await prop.adelete()
    return {"ok": True, "deleted": pk}


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@api.get("/property-categories/")
async def property_categories(request):
    return {
        "categories": _category_options(),
        "all_token": ALL_CATEGORIES,
    }


@api.get("/property/{pk}/")
async def public_detail(request):
    pk = param_int(request, "pk")
    prop = await _get_property(pk)
    from core.bolt import get_user

    user = await get_user(request)
    is_favorite = False
    if user is not None and user.is_renter:
        is_favorite = await Favorite.objects.filter(user=user, property=prop).aexists()
    return {
        "property": await serialize_property(prop, is_favorite=is_favorite),
        "is_favorite": is_favorite,
        "viewer_is_owner": bool(user is not None and user.is_owner),
    }


mark_full_request(api)

__all__ = ["api"]
