"""Bookings JSON endpoints: renter requests and owner decisions.

Handlers are native async Django-Bolt handlers; the sync booking services
(``pay_booking``, ``transition_booking``) hop through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from django.db.models import Count
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from bookings.helpers import (
    apply_status_filter,
    booking_owner_queryset,
    booking_renter_queryset,
)
from bookings.models import Booking, BookingStatus
from core.bolt import (
    body_str,
    in_thread,
    json_body,
    mark_full_request,
    owner_required,
    param_int,
    q,
    renter_required,
)
from core.bolt_serializers import booking as serialize_booking
from core.bolt_serializers import payment as serialize_payment
from payments.models import Payment
from payments.services import pay_booking, transition_booking

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


async def _status_counts(base_queryset) -> dict:
    counts = {
        row["status"]: row["n"]
        async for row in base_queryset.values("status").annotate(n=Count("id"))
    }
    counts["all"] = sum(counts.values())
    return counts


async def _get_booking(pk: int) -> Booking:
    booking = await (
        Booking.objects.select_related("property", "renter", "owner", "payment")
        .filter(pk=pk)
        .afirst()
    )
    if booking is None:
        raise HTTPException(status_code=404, detail="booking_not_found")
    return booking


async def _renter_booking(pk: int, user) -> Booking:
    booking = await _get_booking(pk)
    if booking.renter_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    return booking


async def _owner_booking(pk: int, user) -> Booking:
    booking = await _get_booking(pk)
    if booking.owner_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    return booking


# ---------------------------------------------------------------------------
# Renter
# ---------------------------------------------------------------------------


@api.get("/rent/bookings/")
async def renter_list(request):
    user = await renter_required(request)
    base = booking_renter_queryset(user)
    queryset = apply_status_filter(base, q(request, "status", "all"))
    return {
        "bookings": [await serialize_booking(b) async for b in queryset],
        "counts": await _status_counts(base),
        "status": q(request, "status", "all"),
    }


@api.get("/rent/bookings/{pk}/")
async def renter_detail(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    booking = await _renter_booking(pk, user)
    return {"booking": await serialize_booking(booking), "audience": "renter"}


@api.post("/rent/bookings/{pk}/cancel/")
async def renter_cancel(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    booking = await _renter_booking(pk, user)
    ok, code = await in_thread(
        transition_booking, booking, BookingStatus.CANCELLED, actor=user
    )
    if not ok:
        raise HTTPException(status_code=409, detail=code)
    return {"ok": True, "booking": await serialize_booking(booking)}


@api.post("/rent/bookings/{pk}/confirm/")
async def renter_confirm(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    booking = await _renter_booking(pk, user)
    ok, code = await in_thread(
        transition_booking, booking, BookingStatus.CONFIRMED, actor=user
    )
    if not ok:
        raise HTTPException(status_code=409, detail=code)
    return {"ok": True, "booking": await serialize_booking(booking)}


@api.post("/rent/bookings/{pk}/pay/")
async def renter_pay(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    booking = await _renter_booking(pk, user)

    if booking.status not in (BookingStatus.APPROVED, BookingStatus.CONFIRMED):
        raise HTTPException(status_code=409, detail="invalid_transition")
    if booking.payment_id:
        return {
            "payment": await serialize_payment(booking.payment),
            "already_paid": True,
        }

    data = json_body(request)
    method = body_str(data, "method") or Payment.Method.ABA
    payment = await in_thread(
        pay_booking,
        booking=booking,
        method=method,
        simulate=body_str(data, "simulate"),
    )
    if not payment.is_successful:
        raise HTTPException(status_code=402, detail="payment_failed")
    return {"payment": await serialize_payment(payment), "already_paid": False}


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------


@api.get("/owner/bookings/")
async def owner_list(request):
    user = await owner_required(request)
    base = booking_owner_queryset(user)
    queryset = apply_status_filter(base, q(request, "status", "all"))
    return {
        "bookings": [await serialize_booking(b) async for b in queryset],
        "counts": await _status_counts(base),
        "status": q(request, "status", "all"),
    }


@api.get("/owner/bookings/{pk}/")
async def owner_detail(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    booking = await _owner_booking(pk, user)
    return {"booking": await serialize_booking(booking), "audience": "owner"}


@api.post("/owner/bookings/{pk}/approve/")
async def owner_approve(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    booking = await _owner_booking(pk, user)
    ok, code = await in_thread(
        transition_booking, booking, BookingStatus.APPROVED, actor=user
    )
    if not ok:
        raise HTTPException(status_code=409, detail=code)
    return {"ok": True, "booking": await serialize_booking(booking)}


@api.post("/owner/bookings/{pk}/reject/")
async def owner_reject(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    booking = await _owner_booking(pk, user)
    ok, code = await in_thread(
        transition_booking, booking, BookingStatus.REJECTED, actor=user
    )
    if not ok:
        raise HTTPException(status_code=409, detail=code)
    return {"ok": True, "booking": await serialize_booking(booking)}


mark_full_request(api)

__all__ = ["api"]
