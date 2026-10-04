from __future__ import annotations

from django.db.models import Avg, Count, Sum
from django.shortcuts import redirect, render

from .decorators import http_methods
from .i18n import Translator


def landing(request):
    """Public marketing / entry page (the web counterpart of onboarding + splash)."""
    if request.user.is_authenticated:
        return redirect(request.user.home_url)

    from bookings.models import Booking, BookingStatus
    from listings.models import Property
    from payments.models import Payment

    t: Translator = getattr(request, "translator", None) or Translator("en")

    stats = {
        "properties": Property.objects.count(),
        "owners": Property.objects.values("owner_id").distinct().count(),
        "bookings": Booking.objects.count(),
        "cities": Property.objects.values("location").distinct().count(),
        "renters": Property.objects.count(),
    }
    featured = list(Property.objects.select_related("owner").order_by("-created_at")[:3])
    avg_price = Property.objects.aggregate(v=Avg("price_per_month"))["v"] or 0
    revenue = Payment.objects.filter(status=Payment.Status.SUCCESS).aggregate(v=Sum("amount"))["v"] or 0

    stats_list = [
        ("properties", t("properties"), stats["properties"], "building"),
        ("owners", t("property_owner"), stats["owners"], "store"),
        ("bookings", t("bookings"), stats["bookings"], "clipboard"),
        ("cities", t("location"), stats["cities"], "map-pin"),
    ]

    feature_list = [
        (
            "sliders",
            t("web_feature_listings"),
            t("search_placeholder") + " · " + t("filter_properties"),
        ),
        (
            "clipboard",
            t("web_feature_booking"),
            t("send_booking_request") + " · " + t("approve") + " / " + t("reject"),
        ),
        (
            "card",
            t("web_feature_payments"),
            t("method_aba") + " · " + t("refund_status"),
        ),
        (
            "shield-admin",
            t("web_feature_admin"),
            t("users") + " · " + t("bookings") + " · " + t("payments"),
        ),
    ]

    return render(
        request,
        "core/landing.html",
        {
            "stats": stats,
            "stats_list": stats_list,
            "feature_list": feature_list,
            "featured": featured,
            "avg_price": avg_price,
            "revenue": revenue,
            "has_data": Property.objects.exists() and Booking.objects.exists(),
        },
    )


def health(request):
    from django.http import JsonResponse

    from accounts.models import User
    from bookings.models import Booking, BookingStatus
    from listings.models import Property
    from payments.models import Payment

    return JsonResponse(
        {
            "status": "ok",
            "users": User.objects.count(),
            "properties": Property.objects.count(),
            "bookings": Booking.objects.count(),
            "payments": Payment.objects.count(),
            "bookings_pending": Booking.objects.filter(status=BookingStatus.PENDING).count(),
        }
    )


@http_methods("POST")
def dismiss_tour(request):
    request.session["renteasy_seen_tour"] = True
    return redirect(request.POST.get("next") or "/")


def not_found(request, exception=None):
    from django.http import HttpResponseNotFound

    return HttpResponseNotFound(render(request, "errors/404.html", status=404).content)


def server_error(request):
    from django.http import HttpResponseServerError

    return HttpResponseServerError(render(request, "errors/500.html", status=500).content)


def permission_denied(request, exception=None):
    from django.http import HttpResponseForbidden

    return HttpResponseForbidden(render(request, "errors/403.html", status=403).content)
