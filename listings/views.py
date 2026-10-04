from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
from core.decorators import http_methods, role_guard
from core.i18n import Translator
from notifications.services import notify
from payments.models import Payment

from .forms import BookingRequestForm, PropertyFilterForm, PropertyForm
from .models import Favorite, Property

ALL_LOCATIONS = "__all__"
MAX_PRICE_CEILING = Decimal("5000")
MIN_PRICE_FLOOR = Decimal("300")


@require_GET
@login_required
@role_guard("is_renter")
def renter_browse(request):
    """Property listing screen: search, filter, sort (web PropertyListScreen)."""
    form = PropertyFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    if not form.is_valid():
        form = PropertyFilterForm()

    queryset = (
        Property.objects.select_related("owner")
        .filter(owner__role=Role.OWNER)
        .for_renter(request.user)
        .annotate(favorite_count=_count_favorites(), booking_count=_count_bookings())
    )

    query = (data.get("q") or "").strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(location__icontains=query) | Q(description__icontains=query))

    location = (data.get("location") or "").strip()
    if location and location != ALL_LOCATIONS:
        queryset = queryset.filter(location__iexact=location)

    min_bedrooms = data.get("min_bedrooms") or 0
    if min_bedrooms:
        queryset = queryset.filter(bedrooms__gte=min_bedrooms)

    max_price = data.get("max_price")
    if max_price is not None:
        queryset = queryset.filter(price_per_month__lte=Decimal(str(max_price)))

    sort = data.get("sort", "recommended")
    if sort == "price_low":
        queryset = queryset.order_by("price_per_month", "title")
    elif sort == "price_high":
        queryset = queryset.order_by("-price_per_month", "title")
    elif sort == "bedrooms":
        queryset = queryset.order_by("-bedrooms", "price_per_month")
    else:
        queryset = queryset.order_by("-created_at", "title")

    properties = list(queryset)
    favorite_ids = set(
        Favorite.objects.filter(user=request.user, property_id__in=[p.pk for p in properties]).values_list(
            "property_id", flat=True
        )
    )
    active_booking_property_ids = set(
        Booking.objects.filter(
            renter=request.user,
            property_id__in=[p.pk for p in properties],
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        ).values_list("property_id", flat=True)
    )

    locations = sorted({loc for loc in Property.objects.values_list("location", flat=True) if loc})
    price_bounds = Property.objects.aggregate(lo=Min("price_per_month"), hi=Max("price_per_month"))

    summary = properties and properties or []
    avg_price = sum(float(p.price_per_month) for p in summary) / len(summary) if summary else 0.0

    return render(
        request,
        "listings/renter_browse.html",
        {
            "properties": properties,
            "favorite_ids": favorite_ids,
            "active_booking_property_ids": active_booking_property_ids,
            "filter_form": form,
            "locations": locations,
            "all_locations_token": ALL_LOCATIONS,
            "avg_price": avg_price,
            "sort_choices": PropertyFilterForm.SORT_CHOICES,
            "price_floor": float(price_bounds["lo"] or MIN_PRICE_FLOOR),
            "price_ceiling": float(price_bounds["hi"] or MAX_PRICE_CEILING),
            "max_ceiling": float(MAX_PRICE_CEILING),
            "query": query,
            "selected_location": location,
            "selected_sort": sort,
            "min_bedrooms": min_bedrooms,
            "max_price": max_price,
        },
    )


def _count_favorites():
    from django.db.models import Count

    return Count("favorites", distinct=True)


def _count_bookings():
    from django.db.models import Count

    return Count("bookings", distinct=True)


@require_GET
@login_required
@role_guard("is_renter")
def renter_detail(request, pk: int):
    property_obj = get_object_or_404(Property.objects.select_related("owner"), pk=pk)
    is_favorite = Favorite.objects.filter(user=request.user, property=property_obj).exists()
    active_booking = (
        Booking.objects.filter(
            renter=request.user,
            property=property_obj,
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        )
        .order_by("-created_at")
        .first()
    )
    owner_bookings = Booking.objects.filter(
        property=property_obj, status=BookingStatus.APPROVED
    ).count()
    return render(
        request,
        "listings/renter_detail.html",
        {
            "property": property_obj,
            "is_favorite": is_favorite,
            "active_booking": active_booking,
            "owner_bookings": owner_bookings,
        },
    )


@require_GET
@login_required
@role_guard("is_renter")
def renter_favorites(request):
    favorite_rows = (
        Favorite.objects.filter(user=request.user)
        .select_related("property", "property__owner")
        .order_by("-created_at")
    )
    favorite_ids = set(favorite_rows.values_list("property_id", flat=True))
    favorites = list(
        Property.objects.filter(pk__in=favorite_ids)
        .select_related("owner")
        .for_renter(request.user)
        .annotate(favorite_count=_count_favorites(), booking_count=_count_bookings())
        .order_by("-created_at")
    )
    return render(
        request,
        "listings/renter_favorites.html",
        {"favorites": favorites, "favorite_ids": favorite_ids},
    )


@require_POST
@login_required
@role_guard("is_renter")
def toggle_favorite(request, pk: int):
    property_obj = get_object_or_404(Property, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, property=property_obj)
    if not created:
        favorite.delete()
        created = False

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorited": created, "count": Favorite.objects.filter(property=property_obj).count()})
    return redirect(request.POST.get("next") or reverse("listings:renter_favorites"))


@http_methods("GET", "POST")
@login_required
@role_guard("is_renter")
def booking_request(request, pk: int):
    from payments.services import create_booking

    property_obj = get_object_or_404(Property.objects.select_related("owner"), pk=pk)

    if request.method == "POST":
        form = BookingRequestForm(request.POST)
        if form.is_valid():
            booking = create_booking(
                property_obj=property_obj,
                renter=request.user,
                move_in_date=form.cleaned_data.get("move_in_date"),
                lease_months=form.cleaned_data.get("lease_months") or 12,
                note=form.cleaned_data.get("note") or "",
            )
            if booking is None:
                request.session["renteasy_flash"] = "active_booking_exists"
                return redirect("listings:renter_detail", pk=pk)
            request.session["renteasy_flash"] = "booking_sent"
            return redirect("bookings:renter_list")
    else:
        form = BookingRequestForm()

    return render(
        request,
        "listings/booking_request.html",
        {"property": property_obj, "form": form},
    )


# ---------------------------------------------------------------------------
# Owner portal
# ---------------------------------------------------------------------------


@require_GET
@login_required
@role_guard("is_owner")
def owner_list(request):
    properties = (
        Property.objects.filter(owner=request.user)
        .annotate(favorite_count=_count_favorites(), booking_count=_count_bookings())
        .order_by("-created_at")
    )
    return render(request, "listings/owner_list.html", {"properties": properties})


@http_methods("GET", "POST")
@login_required
@role_guard("is_owner")
def owner_create(request):
    form = PropertyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        property_obj = form.save(commit=False)
        property_obj.owner = request.user
        property_obj.save()
        request.session["renteasy_flash"] = "property_created"
        return redirect("listings:owner_list")
    return render(
        request,
        "listings/owner_form.html",
        {"form": form, "mode": "create", "title_key": "add_property", "submit_key": "save_property"},
    )


@http_methods("GET", "POST")
@login_required
@role_guard("is_owner")
def owner_edit(request, pk: int):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    form = PropertyForm(request.POST or None, instance=property_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.session["renteasy_flash"] = "property_updated"
        return redirect("listings:owner_list")
    return render(
        request,
        "listings/owner_form.html",
        {"form": form, "mode": "edit", "property": property_obj, "title_key": "edit_property", "submit_key": "save_changes"},
    )


@require_POST
@login_required
@role_guard("is_owner")
def owner_delete(request, pk: int):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    property_obj.delete()
    request.session["renteasy_flash"] = "property_deleted"
    return redirect("listings:owner_list")


@require_GET
def public_detail(request, pk: int):
    """Signed-out visitors can inspect a listing (no booking actions)."""
    property_obj = get_object_or_404(Property.objects.select_related("owner"), pk=pk)
    if request.user.is_authenticated and request.user.is_owner:
        return redirect("listings:owner_edit", pk=pk)
    return render(
        request,
        "listings/public_detail.html",
        {"property": property_obj, "is_favorite": False, "active_booking": None},
    )
