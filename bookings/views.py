from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import http_methods, role_guard
from core.i18n import Translator
from payments.models import Payment
from payments.services import pay_booking, transition_booking

from .helpers import (
    BOOKING_STATUS_FILTERS,
    BookingFilter,
    PayBookingForm,
    apply_status_filter,
    booking_owner_queryset,
    booking_renter_queryset,
    focus_queryset,
    get_booking_for,
    redirect_back,
)
from .models import Booking, BookingStatus


@require_GET
@login_required
@role_guard("is_renter")
def renter_list(request):
    flt = BookingFilter(request)
    queryset = apply_status_filter(booking_renter_queryset(request.user), flt.status)
    bookings = list(queryset)
    counts = _status_counts(booking_renter_queryset(request.user))
    return render(
        request,
        "bookings/renter_list.html",
        {
            "bookings": bookings,
            "flt": flt,
            "counts": counts,
            "focus": flt.focus,
            "filter_keys": list(BOOKING_STATUS_FILTERS[1:]),
        },
    )


@require_GET
@login_required
@role_guard("is_renter")
def renter_detail(request, pk: int):
    booking = get_booking_for(pk)
    if booking.renter_id != request.user.pk:
        return render(request, "accounts/denied.html", status=403)
    return render(request, "bookings/detail.html", {"booking": booking, "audience": "renter"})


@require_POST
@login_required
@role_guard("is_renter")
def renter_cancel(request, pk: int):
    booking = get_booking_for(pk)
    if booking.renter_id != request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect_back(request, "bookings:renter_list")
    ok, code = transition_booking(booking, BookingStatus.CANCELLED, actor=request.user)
    request.session["renteasy_flash"] = "booking_cancelled" if ok else code
    return redirect_back(request, "bookings:renter_list")


@http_methods("GET", "POST")
@login_required
@role_guard("is_renter")
def renter_pay(request, pk: int):
    """Mock checkout for an approved booking (Pay Now)."""
    booking = get_booking_for(pk)
    if booking.renter_id != request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect_back(request, "bookings:renter_list")

    if booking.status != BookingStatus.APPROVED:
        request.session["renteasy_flash"] = "invalid_transition"
        return redirect_back(request, "bookings:renter_list")
    if booking.payment_id:
        return redirect("payments:renter_detail", pk=booking.payment_id)

    if request.method == "POST":
        form = PayBookingForm(request.POST)
        if form.is_valid():
            payment = pay_booking(
                booking=booking,
                method=form.cleaned_data["method"],
                simulate=form.cleaned_data.get("simulate") or "",
            )
            if payment.is_successful:
                request.session["renteasy_flash"] = "payment_recorded"
                return redirect("payments:renter_detail", pk=payment.pk)
            request.session["renteasy_flash"] = "payment_failed"
            return redirect("bookings:renter_detail", pk=booking.pk)
    else:
        form = PayBookingForm()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": False}, status=400)
    t: Translator = getattr(request, "translator", None) or Translator("en")
    method_meta = {
        Payment.Method.ABA: ("method_aba", "layers"),
        Payment.Method.WING: ("method_wing", "send"),
        Payment.Method.CARD: ("method_card", "card"),
    }
    method_value = form["method"].value() or ""
    method_choices = [
        {
            "value": value,
            "label": t(method_meta[value][0]),
            "icon": method_meta[value][1],
            "checked": method_value == value or (not method_value and idx == 0),
        }
        for idx, (value, _label) in enumerate(form.fields["method"].choices)
    ]
    return render(
        request,
        "bookings/pay.html",
        {
            "booking": booking,
            "form": form,
            "audience": "renter",
            "method_choices": method_choices,
        },
    )


# ---------------------------------------------------------------------------
# Owner portal
# ---------------------------------------------------------------------------


@require_GET
@login_required
@role_guard("is_owner")
def owner_list(request):
    flt = BookingFilter(request)
    queryset = apply_status_filter(booking_owner_queryset(request.user), flt.status)
    bookings = list(queryset)
    counts = _status_counts(booking_owner_queryset(request.user))
    return render(
        request,
        "bookings/owner_list.html",
        {
            "bookings": bookings,
            "flt": flt,
            "counts": counts,
            "focus": flt.focus,
            "filter_keys": list(BOOKING_STATUS_FILTERS[1:]),
        },
    )


@require_GET
@login_required
@role_guard("is_owner")
def owner_detail(request, pk: int):
    booking = get_booking_for(pk)
    if booking.owner_id != request.user.pk:
        return render(request, "accounts/denied.html", status=403)
    return render(request, "bookings/detail.html", {"booking": booking, "audience": "owner"})


@require_POST
@login_required
@role_guard("is_owner")
def owner_approve(request, pk: int):
    booking = get_booking_for(pk)
    if booking.owner_id != request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect_back(request, "bookings:owner_list")
    ok, code = transition_booking(booking, BookingStatus.APPROVED, actor=request.user)
    request.session["renteasy_flash"] = "booking_approved" if ok else code
    return redirect_back(request, "bookings:owner_list")


@require_POST
@login_required
@role_guard("is_owner")
def owner_reject(request, pk: int):
    booking = get_booking_for(pk)
    if booking.owner_id != request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect_back(request, "bookings:owner_list")
    ok, code = transition_booking(booking, BookingStatus.REJECTED, actor=request.user)
    request.session["renteasy_flash"] = "booking_rejected" if ok else code
    return redirect_back(request, "bookings:owner_list")


def _status_counts(base_queryset) -> dict:
    rows = (
        base_queryset.values("status")
        .annotate(n=Count("id"))
    )
    counts = {row["status"]: row["n"] for row in rows}
    counts["all"] = sum(counts.values())
    return counts


def api_notify_state(request):
    """Tiny endpoint used by jQuery to refresh the bell badge after an action."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False})
    return JsonResponse({"ok": True, "user": request.user.display_name})
