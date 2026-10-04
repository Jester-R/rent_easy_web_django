from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from bookings.models import Booking, BookingStatus
from core.i18n import Translator
from listings.models import Favorite, Property
from payments.models import Payment, Refund

from .models import User
from .views import owner_required, renter_required, superadmin_required


@login_required
@renter_required
def renter_dashboard(request):
    user = request.user
    properties = Property.objects.filter(owner__role="owner").order_by("-created_at")
    bookings = (
        Booking.objects.filter(renter=user)
        .select_related("property", "owner", "payment")
        .order_by("-created_at")
    )
    payments = Payment.objects.filter(user=user).order_by("-created_at")
    favorites = Favorite.objects.filter(user=user).select_related("property")

    counts = {row["status"]: row["n"] for row in bookings.values("status").annotate(n=Count("id"))}
    spend = payments.filter(status=Payment.Status.SUCCESS).aggregate(v=Sum("amount"))["v"] or 0
    refunded = payments.aggregate(v=Sum("refunded_amount"))["v"] or 0

    featured = properties[:3]
    suggested = properties.exclude(
        id__in=Booking.objects.filter(
            renter=user, status__in=[BookingStatus.PENDING, BookingStatus.APPROVED]
        ).values_list("property_id", flat=True)
    )[:6]

    return render(
        request,
        "dashboards/renter.html",
        {
            "stats": {
                "available": properties.count(),
                "bookings": bookings.count(),
                "active": counts.get(BookingStatus.PENDING, 0) + counts.get(BookingStatus.APPROVED, 0),
                "pending": counts.get(BookingStatus.PENDING, 0),
                "approved": counts.get(BookingStatus.APPROVED, 0),
                "favorites": favorites.count(),
                "payments": payments.count(),
                "spend": float(spend),
                "refunded": float(refunded),
            },
            "featured": featured,
            "suggested": suggested,
            "recent_bookings": bookings[:5],
            "recent_payments": payments[:5],
            "favorite_ids": set(favorites.values_list("property_id", flat=True)),
        },
    )


@login_required
@owner_required
def owner_dashboard(request):
    user = request.user
    properties = Property.objects.filter(owner=user).annotate(
        favorite_count=Count("favorites", distinct=True),
        booking_count=Count("bookings", distinct=True),
        revenue=Sum("payments__amount", filter=Q(payments__status=Payment.Status.SUCCESS)),
    ).order_by("-created_at")
    bookings = (
        Booking.objects.filter(owner=user)
        .select_related("property", "renter", "payment")
        .order_by("-created_at")
    )
    payments = Payment.objects.filter(property__owner=user).order_by("-created_at")

    counts = {row["status"]: row["n"] for row in bookings.values("status").annotate(n=Count("id"))}
    potential = properties.aggregate(v=Sum("price_per_month"))["v"] or Decimal("0")
    revenue = payments.filter(status=Payment.Status.SUCCESS).aggregate(v=Sum("amount"))["v"] or 0
    pending_refunds = Refund.objects.filter(booking__owner=user, status=Refund.Status.PENDING).count()

    t: Translator = getattr(request, "translator", None) or Translator("en")
    stats_listings = properties.count()
    stats_bookings = bookings.count()
    stats_payments = payments.count()
    stats_favorites = Favorite.objects.filter(property__owner=user).count()
    money_rows = [
        (t("stat_active_listings"), stats_listings, "building"),
        (t("bookings"), stats_bookings, "clipboard"),
        (t("payments"), stats_payments, "receipt"),
        (t("favorites"), stats_favorites, "heart"),
    ]

    return render(
        request,
        "dashboards/owner.html",
        {
            "stats": {
                "listings": properties.count(),
                "pending": counts.get(BookingStatus.PENDING, 0),
                "approved": counts.get(BookingStatus.APPROVED, 0),
                "rejected": counts.get(BookingStatus.REJECTED, 0),
                "cancelled": counts.get(BookingStatus.CANCELLED, 0),
                "potential": float(potential),
                "revenue": float(revenue),
                "favorites": Favorite.objects.filter(property__owner=user).count(),
                "bookings": bookings.count(),
                "payments": payments.count(),
                "pending_refunds": pending_refunds,
            },
            "properties": properties,
            "recent_bookings": bookings[:5],
            "recent_payments": payments[:5],
            "pending_line_key": "pending_requests_line",
            "money_rows": money_rows,
            "focus": request.GET.get("focus"),
        },
    )


@login_required
@superadmin_required
def console_home(request):
    from .console import dashboard

    return dashboard(request)
