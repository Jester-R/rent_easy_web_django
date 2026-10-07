from __future__ import annotations

import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking, BookingStatus
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment, Refund

#: Mirrors ``PaymentService.runMockPayment`` — 90% success, 10% failure.
MOCK_SUCCESS_RATE = 0.90
MOCK_LATENCY_MS = 1200


class MockGateway:
    """Simulated payment gateway (deterministic-friendly 90% success rate)."""

    @staticmethod
    def authorize(amount: Decimal) -> bool:
        return random.random() < MOCK_SUCCESS_RATE

    @staticmethod
    def latency_seconds() -> float:
        return MOCK_LATENCY_MS / 1000.0


@transaction.atomic
def create_booking(
    *, property_obj, renter, move_in_date=None, lease_months: int = 12, note: str = ""
):
    """Create a pending booking request, guarding the active-booking rule."""
    if has_active_booking(renter, property_obj):
        return None
    booking = Booking.objects.create(
        property=property_obj,
        renter=renter,
        owner=property_obj.owner,
        status=BookingStatus.PENDING,
        monthly_rent=property_obj.price_per_month,
        move_in_date=move_in_date,
        lease_months=lease_months,
        note=(note or "").strip(),
    )
    notify(
        property_obj.owner,
        Notification.Kind.BOOKING_REQUEST,
        "notif_new_request",
        "notif_new_request_body",
        params={"renter": renter.display_name, "title": property_obj.title},
        link=booking.get_absolute_url(),
        action="owner_decision",
    )
    return booking


def has_active_booking(renter, property_obj) -> bool:
    return Booking.objects.filter(
        renter=renter,
        property=property_obj,
        status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
    ).exists()


@transaction.atomic
def transition_booking(
    booking: Booking, new_status: str, actor=None
) -> tuple[bool, str]:
    """Apply a validated booking transition and notify both parties."""
    if not booking.can_transition_to(new_status):
        return False, "invalid_transition"

    previous = booking.status
    ok = booking.transition(new_status)
    if not ok:
        return False, "invalid_transition"

    if new_status == BookingStatus.APPROVED:
        notify(
            booking.renter,
            Notification.Kind.BOOKING_APPROVED,
            "notif_booking_approved",
            "notif_booking_approved_body",
            params={"title": booking.property_title},
            link=booking.get_absolute_url(),
            action="renter_pay_now",
        )
    elif new_status == BookingStatus.REJECTED:
        notify(
            booking.renter,
            Notification.Kind.BOOKING_UPDATE,
            "notif_booking_rejected",
            "notif_booking_rejected_body",
            params={"title": booking.property_title},
            link=booking.get_absolute_url(),
        )
        queue_refund(booking, Refund.Reason.REJECTED_BY_OWNER, actor=actor)
    elif new_status == BookingStatus.CANCELLED:
        notify(
            booking.owner,
            Notification.Kind.BOOKING_UPDATE,
            "notif_booking_cancelled",
            "notif_booking_cancelled_body",
            params={"title": booking.property_title},
            link=booking.get_absolute_url(),
        )
        queue_refund(booking, Refund.Reason.CANCELLED_BY_RENTER, actor=actor)

    if previous != new_status:
        notify(
            booking.owner,
            Notification.Kind.BOOKING_UPDATE,
            "notif_booking_update",
            "notif_booking_update_body",
            params={"title": booking.property_title, "status": new_status},
            link=booking.get_absolute_url(),
        )
    return True, ""


@transaction.atomic
def pay_booking(*, booking: Booking, method: str, simulate: str = "") -> Payment:
    """Run the mock gateway and attach the resulting payment to ``booking``."""
    force = (simulate or "").strip().lower()
    if force == "success":
        success = True
    elif force == "failed":
        success = False
    else:
        success = MockGateway.authorize(booking.monthly_rent)

    payment = Payment.objects.create(
        property=booking.property,
        user=booking.renter,
        booking=booking,
        amount=booking.monthly_rent,
        method=method,
        status=Payment.Status.SUCCESS if success else Payment.Status.FAILED,
    )
    if success:
        booking.payment = payment
        booking.save(update_fields=["payment"])
        notify(
            booking.owner,
            Notification.Kind.PAYMENT_RECEIVED,
            "notif_payment_received",
            "notif_payment_received_body",
            params={
                "renter": booking.renter.display_name,
                "amount": payment.amount_display,
                "title": booking.property_title,
            },
            link=booking.get_absolute_url(),
        )
    return payment


@transaction.atomic
def queue_refund(booking: Booking, reason: str, actor=None) -> Refund | None:
    """Create a pending refund for a booking that already has a payment."""
    payment = booking.payment
    if payment is None or not payment.is_successful or payment.is_refunded:
        return None
    refund = Refund.objects.create(
        payment=payment,
        booking=booking,
        amount=payment.amount,
        reason=reason,
    )
    payment.refund_status = Payment.RefundStatus.PENDING
    payment.save(update_fields=["refund_status"])
    return refund


@transaction.atomic
def process_refund(refund: Refund, actor=None) -> bool:
    if not refund.process():
        return False
    booking = refund.booking
    notify(
        booking.renter,
        Notification.Kind.REFUND_PROCESSED,
        "notif_refund_processed",
        "notif_refund_processed_body",
        params={"amount": refund.amount_display, "title": booking.property_title},
        link=refund.payment.get_absolute_url(),
    )
    return True


def ensure_demo_payment(
    *, booking: Booking, method: str = Payment.Method.ABA
) -> Payment | None:
    """Seed helper: attach a successful payment (used by the demo data command)."""
    if booking.payment_id:
        return booking.payment
    payment = Payment.objects.create(
        property=booking.property,
        user=booking.renter,
        booking=booking,
        amount=booking.monthly_rent,
        method=method,
        status=Payment.Status.SUCCESS,
        created_at=booking.approved_at or timezone.now(),
    )
    booking.payment = payment
    booking.save(update_fields=["payment"])
    return payment
