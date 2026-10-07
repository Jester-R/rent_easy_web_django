"""Reusable queryset builders for the bookings API.

All helpers return lazy querysets, so they are safe to call from async
handlers (no ORM I/O until awaited/iterated).
"""

from __future__ import annotations

from django.db.models import Q

from .models import Booking

BOOKING_STATUS_FILTERS = ("all", "Pending", "Approved", "Rejected", "Cancelled")


def apply_status_filter(queryset, raw: str):
    value = (raw or "all").strip()
    if value in BOOKING_STATUS_FILTERS and value != "all":
        return queryset.filter(status=value)
    return queryset


def booking_owner_queryset(user):
    return (
        Booking.objects.filter(owner=user)
        .select_related("property", "renter", "owner", "payment")
        .order_by("-created_at")
    )


def booking_renter_queryset(user):
    return (
        Booking.objects.filter(renter=user)
        .select_related("property", "renter", "owner", "payment")
        .order_by("-created_at")
    )


def booking_all_queryset():
    return Booking.objects.select_related(
        "property", "renter", "owner", "payment"
    ).order_by("-created_at")


def search_bookings(queryset, query: str):
    query = (query or "").strip()
    if not query:
        return queryset
    return queryset.filter(
        Q(property__title__icontains=query)
        | Q(renter__email__icontains=query)
        | Q(renter__full_name__icontains=query)
        | Q(owner__email__icontains=query)
        | Q(owner__full_name__icontains=query)
    )