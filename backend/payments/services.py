from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
from notifications.models import Notification
from notifications.services import notify
from payments.gateways import aba as aba_gateway
from payments.models import Payment, Payout, Refund

logger = logging.getLogger(__name__)


class RefundRequiresGateway(RuntimeError):
    """Raised when a real gateway payment cannot be refunded locally."""

    code = "refund_requires_payway_portal"


class RefundRequestError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PayoutNotDue(RuntimeError):
    code = "payout_not_due"


class PayoutBlocked(RuntimeError):
    code = "payout_blocked"


class PayoutDetailsMissing(RuntimeError):
    code = "payout_details_missing"


def hold_days() -> int:
    return max(0, int(getattr(settings, "RENT_HOLD_DAYS", 7) or 0))


#: Mirrors ``PaymentService.runMockPayment`` — 90% success, 10% failure.
MOCK_SUCCESS_RATE = 0.90
MOCK_LATENCY_MS = 1200

#: Accept the Flutter wire values (``aba``/``wing``/``card``) as well as the
#: canonical labels already stored in the database.
_METHOD_ALIASES: dict[str, str] = {
    "aba": Payment.Method.ABA,
    "aba pay": Payment.Method.ABA,
    "aba pay (mock)": Payment.Method.ABA_MOCK,
    "wing": Payment.Method.WING,
    "wing (mock)": Payment.Method.WING,
    "card": Payment.Method.CARD,
    "credit card": Payment.Method.CARD,
    "credit card (mock)": Payment.Method.CARD,
}


def normalize_method(value: str | None, default: str = Payment.Method.ABA) -> str:
    """Map a client-supplied payment method onto a canonical ``Method`` value."""
    if not value:
        return default
    return _METHOD_ALIASES.get(str(value).strip().lower(), default)


@dataclass
class PaymentResult:
    """Outcome of starting a booking payment.

    ``checkout`` is set when the renter must be redirected to a hosted gateway
    page; ``payment.status`` is then ``Pending`` until the callback or a
    reconciliation call confirms it.
    """

    payment: Payment
    checkout: dict | None = None


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
    *,
    property_obj,
    renter,
    move_in_date=None,
    end_date=None,
    lease_months: int = 12,
    note: str = "",
):
    """Create a pending booking request, guarding the active-booking rule."""
    from listings.models import Property

    Property.objects.select_for_update().get(pk=property_obj.pk)
    if has_active_booking(renter, property_obj):
        return None
    if Booking.objects.filter(
        property=property_obj, status=BookingStatus.CONFIRMED
    ).exists():
        return None
    booking = Booking.objects.create(
        property=property_obj,
        renter=renter,
        owner=property_obj.owner,
        status=BookingStatus.PENDING,
        monthly_rent=property_obj.price_per_month,
        move_in_date=move_in_date,
        end_date=end_date,
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
        status__in=[
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
        ],
    ).exists()


def payout_for_payment(payment: Payment | None) -> Payout | None:
    if payment is None or not payment.pk:
        return None
    return Payout.objects.filter(payment_id=payment.pk).first()


def cancellation_window_open(booking: Booking) -> bool:
    """Whether a paid booking may still be cancelled and refunded.

    The platform holds the money for :data:`RENT_HOLD_DAYS`. Once that window
    closes the owner is entitled to the payout, so cancellation/refund is no
    longer automatic. Legacy payments without a payout row keep the old
    behaviour.
    """
    if not booking.payment_id:
        return True
    payout = payout_for_payment(booking.payment)
    if payout is None:
        return True
    return (
        payout.status == Payout.Status.SCHEDULED
        and payout.available_at > timezone.now()
    )


@transaction.atomic
def transition_booking(
    booking: Booking, new_status: str, actor=None
) -> tuple[bool, str]:
    """Apply a validated booking transition and notify both parties."""
    if (
        new_status in (BookingStatus.CANCELLED, BookingStatus.REJECTED)
        and booking.payment_id
        and not cancellation_window_open(booking)
    ):
        return False, "payout_released"
    if not booking.can_transition_to(new_status):
        return False, "invalid_transition"

    if new_status in (BookingStatus.APPROVED, BookingStatus.CONFIRMED):
        from listings.models import Property

        Property.objects.select_for_update().get(pk=booking.property_id)
        if (
            Booking.objects.filter(
                property_id=booking.property_id, status=BookingStatus.CONFIRMED
            )
            .exclude(pk=booking.pk)
            .exists()
        ):
            return False, "property_already_confirmed"

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
    elif new_status == BookingStatus.CONFIRMED:
        notify(
            booking.owner,
            Notification.Kind.BOOKING_UPDATE,
            "notif_renter_confirmed",
            "notif_renter_confirmed_body",
            params={
                "title": booking.property_title,
                "renter": booking.renter.display_name,
            },
            link=booking.get_absolute_url(),
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
        recipient = (
            booking.renter
            if actor is not None and getattr(actor, "is_owner", False)
            else booking.owner
        )
        notify(
            recipient,
            Notification.Kind.BOOKING_UPDATE,
            "notif_booking_cancelled",
            "notif_booking_cancelled_body",
            params={"title": booking.property_title},
            link=booking.get_absolute_url(),
        )
        reason = (
            Refund.Reason.CANCELLED_BY_OWNER
            if actor is not None and getattr(actor, "is_owner", False)
            else Refund.Reason.CANCELLED_BY_RENTER
        )
        queue_refund(booking, reason, actor=actor)

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
def pay_booking(*, booking: Booking, method: str, simulate: str = "") -> PaymentResult:
    """Start a booking payment.

    Real ABA PayWay is used whenever credentials are configured. Simulated
    outcomes only apply to the demo methods (and to ``ABA Pay`` when the
    gateway is disabled), so a client cannot fake a real payment.
    """
    canonical = normalize_method(method)
    force = (simulate or "").strip().lower()

    # Never let a client "simulate" success for a configured real gateway: that
    # would mark the booking paid without a PayWay transaction. Disable the
    # gateway (ABA_PAYWAY_ENABLED=false) to use the demo flow instead.
    if canonical == Payment.Method.ABA and aba_gateway.is_configured():
        return _start_aba_payment(booking)

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
        method=(
            Payment.Method.ABA_MOCK if canonical == Payment.Method.ABA else canonical
        ),
        status=Payment.Status.SUCCESS if success else Payment.Status.FAILED,
        provider=Payment.Provider.MOCK,
        paid_at=timezone.now() if success else None,
    )
    if success:
        _attach_successful_payment(booking, payment)
    return PaymentResult(payment)


@transaction.atomic
def _start_aba_payment(booking: Booking) -> PaymentResult:
    """Create a pending payment and the signed PayWay checkout form."""
    payment = Payment.objects.create(
        property=booking.property,
        user=booking.renter,
        booking=booking,
        amount=booking.monthly_rent,
        method=Payment.Method.ABA,
        status=Payment.Status.PENDING,
        provider=Payment.Provider.ABA_PAYWAY,
    )
    # The reference is generated in ``save``; use it as the PayWay tran_id so
    # the callback can find this row without trusting client input.
    payment.provider_ref = payment.reference
    payment.save(update_fields=["provider_ref"])

    renter = booking.renter
    firstname, lastname = _payway_name_parts(renter.display_name)
    items = [
        {
            "name": booking.property_title,
            "quantity": 1,
            "price": float(payment.amount),
        }
    ]
    return_params = json.dumps({"payment_id": payment.pk}, separators=(",", ":"))

    try:
        checkout = aba_gateway.create_purchase_form(
            tran_id=payment.provider_ref,
            amount=payment.amount,
            firstname=firstname,
            lastname=lastname,
            email=renter.email,
            phone="",
            items=items,
            return_params=return_params,
        )
    except Exception as exc:
        payment.status = Payment.Status.FAILED
        payment.gateway_payload = {
            "error": str(exc),
            "code": getattr(exc, "code", ""),
        }
        payment.save(update_fields=["status", "gateway_payload"])
        raise

    payment.gateway_payload = {
        "request": {
            key: value for key, value in checkout["fields"].items() if key != "hash"
        },
    }
    payment.save(update_fields=["gateway_payload"])
    return PaymentResult(payment, checkout=checkout)


def _payway_name_parts(display_name: str) -> tuple[str, str]:
    """PayWay rejects names containing digits/special characters."""
    parts = [re.sub(r"[^A-Za-z]", "", part) for part in (display_name or "").split()]
    parts = [part for part in parts if part]
    firstname = parts[0] if parts else "RentEasy"
    lastname = parts[-1] if len(parts) > 1 else "Renter"
    return firstname[:100], lastname[:100]


def _attach_successful_payment(booking: Booking, payment: Payment) -> None:
    """Link a successful payment to its booking and alert the owner."""
    booking.payment = payment
    booking.save(update_fields=["payment"])
    create_payout_for_payment(payment)
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
        link=payment.get_absolute_url(),
    )


def _payout_snapshot(owner) -> dict[str, str]:
    return {
        "payout_method": owner.payout_method or "",
        "payout_account_name": owner.payout_account_name or "",
        "payout_account_number": owner.payout_account_number or "",
        "payout_bank_name": owner.payout_bank_name or "",
        "payout_phone": owner.payout_phone or "",
    }


@transaction.atomic
def create_payout_for_payment(payment: Payment) -> Payout | None:
    """Schedule the owner payout for a successful payment (idempotent)."""
    if not payment.is_successful or payment.is_refunded:
        return None
    owner = None
    if payment.booking_id:
        owner = payment.booking.owner
    elif payment.property_id:
        owner = payment.property.owner
    if owner is None:
        return None

    paid_at = payment.paid_at or payment.created_at or timezone.now()
    available_at = paid_at + timedelta(days=hold_days())
    payout, created = Payout.objects.get_or_create(
        payment=payment,
        defaults={
            "owner": owner,
            "amount": payment.amount,
            "status": Payout.Status.SCHEDULED,
            "available_at": available_at,
            **_payout_snapshot(owner),
        },
    )
    if not created and payout.status in (
        Payout.Status.SCHEDULED,
        Payout.Status.ELIGIBLE,
    ):
        # Keep the amount in sync if an admin corrected the payment before the
        # transfer, but never rewrite a paid/cancelled row.
        if payout.amount != payment.amount:
            payout.amount = payment.amount
            payout.save(update_fields=["amount", "updated_at"])
    return payout


@transaction.atomic
def cancel_payout_for_payment(payment: Payment) -> int:
    """Cancel any not-yet-paid payout for a payment (refund/cancellation)."""
    return Payout.objects.filter(
        payment=payment,
        status__in=[Payout.Status.SCHEDULED, Payout.Status.ELIGIBLE],
    ).update(status=Payout.Status.CANCELLED, updated_at=timezone.now())


@transaction.atomic
def release_due_payouts(owner=None) -> int:
    """Move due payouts to ``Eligible`` and cancel blocked ones.

    This is deliberately request-driven (no background worker): every owner or
    admin payout list calls it, so the status is fresh whenever someone looks.
    """
    now = timezone.now()
    base = Payout.objects.filter(
        status__in=[Payout.Status.SCHEDULED, Payout.Status.ELIGIBLE]
    )
    if owner is not None:
        base = base.filter(owner=owner)

    # A cancellation/refund may have happened while the row was scheduled.
    cancelled = {"status": Payout.Status.CANCELLED, "updated_at": now}
    base.filter(payment__status=Payment.Status.FAILED).update(**cancelled)
    base.filter(payment__refund_status=Payment.RefundStatus.PROCESSED).update(
        **cancelled
    )
    base.filter(
        payment__booking__status__in=[
            BookingStatus.CANCELLED,
            BookingStatus.REJECTED,
        ]
    ).update(**cancelled)
    return base.filter(
        status=Payout.Status.SCHEDULED,
        available_at__lte=now,
        payment__status=Payment.Status.SUCCESS,
    ).update(status=Payout.Status.ELIGIBLE, updated_at=now)


def backfill_missing_payouts(owner=None) -> int:
    """Create payout rows for successful payments made before this feature."""
    qs = Payment.objects.filter(
        status=Payment.Status.SUCCESS, payout__isnull=True
    ).select_related("booking", "booking__owner", "property", "property__owner")
    if owner is not None:
        qs = qs.filter(Q(property__owner=owner) | Q(booking__owner=owner))
    count = 0
    for payment in qs[:500]:
        if create_payout_for_payment(payment) is not None:
            count += 1
    return count


@transaction.atomic
def confirm_aba_payment(
    payment_id: int,
    *,
    status: str,
    amount=None,
    payload: dict | None = None,
) -> bool:
    """Reconcile a PayWay transaction with a pending payment row.

    Idempotent: a second callback or refresh returns ``True`` without creating
    another notification. An amount mismatch or a booking that already has a
    different payment marks this transaction failed instead of double-paying.
    """
    payment = (
        Payment.objects.select_for_update()
        .select_related("booking", "booking__renter", "booking__owner", "property")
        .filter(pk=payment_id)
        .first()
    )
    if payment is None or payment.provider != Payment.Provider.ABA_PAYWAY:
        return False
    if payment.is_successful:
        return True

    payload = payload or {}
    status = str(status or "").upper()

    if status in {"DECLINED", "CANCELLED", "FAILED"}:
        if not payment.is_successful:
            payment.status = Payment.Status.FAILED
            payment.gateway_payload = {**payment.gateway_payload, **payload}
            payment.save(update_fields=["status", "gateway_payload"])
        return False

    if not aba_gateway.status_is_approved(status):
        return False

    if amount is not None:
        try:
            paid_amount = Decimal(str(amount))
        except Exception:
            paid_amount = None
        if paid_amount is None or paid_amount != payment.amount:
            payment.status = Payment.Status.FAILED
            payment.gateway_payload = {
                **payment.gateway_payload,
                **payload,
                "error": "amount_mismatch",
                "paid_amount": str(amount),
            }
            payment.save(update_fields=["status", "gateway_payload"])
            return False

    booking = (
        Booking.objects.select_for_update()
        .select_related("property", "renter", "owner")
        .filter(pk=payment.booking_id)
        .first()
    )
    if booking is None:
        return False
    if booking.payment_id and booking.payment_id != payment.pk:
        # The renter was charged for a booking that another transaction has
        # already paid. The money is real, so flag a refund instead of silently
        # treating it as a failed attempt.
        payment.status = Payment.Status.FAILED
        needs_refund = not payment.is_refunded
        if needs_refund:
            payment.refund_status = Payment.RefundStatus.PENDING
        payment.gateway_payload = {
            **payment.gateway_payload,
            **payload,
            "error": "booking_already_paid",
        }
        payment.save(update_fields=["status", "refund_status", "gateway_payload"])
        if needs_refund:
            if not Refund.objects.filter(
                payment=payment, status=Refund.Status.PENDING
            ).exists():
                Refund.objects.create(
                    payment=payment,
                    booking=booking,
                    amount=payment.amount,
                    reason=Refund.Reason.OTHER,
                    note="Duplicate payment for an already-paid booking.",
                )
        return False

    payment.status = Payment.Status.SUCCESS
    payment.paid_at = payment.paid_at or timezone.now()
    payment.gateway_payload = {**payment.gateway_payload, **payload}
    payment.save(update_fields=["status", "paid_at", "gateway_payload"])
    if not booking.payment_id:
        _attach_successful_payment(booking, payment)
    return True


def reconcile_aba_payment(payment: Payment) -> bool:
    """Ask PayWay for the authoritative status and apply it."""
    if payment.provider != Payment.Provider.ABA_PAYWAY or not payment.provider_ref:
        return False
    data = aba_gateway.check_transaction(payment.provider_ref)
    return confirm_aba_payment(
        payment.pk,
        status=str(data.get("payment_status") or ""),
        # ``original_amount`` is in the merchant transaction currency and is
        # not affected by payer-currency conversion or discounts; fall back to
        # the other documented amounts for responses that omit it.
        amount=(
            data.get("original_amount")
            or data.get("total_amount")
            or data.get("payment_amount")
        ),
        payload={"check_transaction": data},
    )


@transaction.atomic
def apply_aba_callback(payload: dict) -> bool:
    """Apply a signature-verified PayWay callback to the matching payment."""
    tran_id = str(payload.get("tran_id") or "").strip()
    if not tran_id:
        return False
    payment = (
        Payment.objects.select_related("booking")
        .filter(provider=Payment.Provider.ABA_PAYWAY, provider_ref=tran_id)
        .first()
    )
    if payment is None:
        return False

    # ``return_params`` round-trips our payment id; reject a callback that was
    # signed for a different transaction.
    return_params = payload.get("return_params")
    if return_params:
        try:
            params = (
                json.loads(return_params)
                if isinstance(return_params, str)
                else return_params
            )
        except ValueError:
            params = {}
        if isinstance(params, dict) and params.get("payment_id"):
            try:
                if int(params["payment_id"]) != payment.pk:
                    return False
            except TypeError, ValueError:
                return False

    callback_code = str(payload.get("status", "")).strip()
    if callback_code in {"0", "00"}:
        status = "APPROVED"
    elif callback_code == "200":
        status = "CANCELLED"
    elif callback_code == "201":
        status = "DECLINED"
    else:
        status = "PENDING"

    amount = (
        payload.get("original_amount")
        or payload.get("total_amount")
        or payload.get("payment_amount")
    )

    # The callback is enough to act on, but the check API is authoritative and
    # also covers callbacks without an amount. Do not fail the callback if the
    # status endpoint is temporarily unreachable.
    try:
        data = aba_gateway.check_transaction(tran_id)
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("ABA PayWay reconciliation failed for %s: %s", tran_id, exc)
    else:
        status = str(data.get("payment_status") or status)
        amount = (
            data.get("original_amount")
            or data.get("total_amount")
            or data.get("payment_amount")
            or amount
        )
        payload = {**payload, "check_transaction": data}

    # Never confirm without an amount: a callback that cannot be checked must
    # stay pending rather than skip amount verification.
    if aba_gateway.status_is_approved(status) and amount is None:
        logger.warning(
            "ABA PayWay callback for %s has no amount; leaving payment pending",
            tran_id,
        )
        return False

    return confirm_aba_payment(
        payment.pk, status=status, amount=amount, payload=payload
    )


@transaction.atomic
def queue_refund(
    booking: Booking, reason: str, actor=None, request_note: str | None = None
) -> Refund | None:
    """Create a pending refund for a booking that already has a payment."""
    payment = booking.payment
    if payment is None or not payment.is_successful or payment.is_refunded:
        return None
    refund = Refund.objects.create(
        payment=payment,
        booking=booking,
        amount=payment.amount,
        reason=reason,
        request_note=request_note
        or f"Refund request created after booking status changed ({reason.replace('_', ' ')}).",
        requested_by=actor,
    )
    payment.refund_status = Payment.RefundStatus.PENDING
    payment.save(update_fields=["refund_status"])
    cancel_payout_for_payment(payment)
    notify_refund_team(refund)
    return refund


def notify_refund_team(refund: Refund) -> None:
    """Notify active administrators that a refund needs review."""
    booking = refund.booking
    admins = User.objects.filter(is_active=True).filter(
        Q(role=Role.SUPERADMIN) | Q(is_staff=True) | Q(is_superuser=True)
    ).distinct()
    for admin in admins:
        notify(
            admin,
            Notification.Kind.REFUND_REQUESTED,
            "notif_refund_requested",
            "notif_refund_requested_body",
            params={
                "amount": refund.amount_display,
                "title": booking.property_title,
                "reference": refund.reference,
            },
            link="/console/payments/",
            action="refund_review",
        )


@transaction.atomic
def request_refund(payment: Payment, requester, reason: str, request_note: str) -> Refund:
    """Queue a payment refund for manual administrator review."""
    payment = (
        Payment.objects.select_for_update()
        .select_related("booking", "booking__owner", "property", "property__owner")
        .get(pk=payment.pk)
    )
    if not payment.is_successful:
        raise RefundRequestError("payment_not_refundable")
    if payment.is_refunded:
        raise RefundRequestError("refund_already_processed")

    booking = payment.booking if payment.booking_id else None
    owner_id = (
        booking.owner_id if booking is not None else
        payment.property.owner_id if payment.property_id else None
    )
    allowed = (
        requester.is_renter and payment.user_id == requester.pk
    ) or (
        requester.is_owner and owner_id == requester.pk
    )
    if not allowed:
        raise RefundRequestError("not_authorized")
    if booking is None:
        raise RefundRequestError("booking_required")
    if requester.is_renter:
        paid_at = payment.paid_at or payment.created_at
        if timezone.now() >= paid_at + timedelta(days=hold_days()):
            raise RefundRequestError("refund_window_closed")
    if payment.refunds.filter(status=Refund.Status.PENDING).exists():
        raise RefundRequestError("refund_already_pending")
    if reason not in Refund.Reason.values:
        raise RefundRequestError("invalid_refund_reason")
    request_note = (request_note or "").strip()
    if not request_note:
        raise RefundRequestError("refund_details_required")

    refund = Refund.objects.create(
        payment=payment,
        booking=booking,
        amount=payment.amount,
        reason=reason,
        request_note=request_note[:5000],
        requested_by=requester,
    )
    payment.refund_status = Payment.RefundStatus.PENDING
    payment.save(update_fields=["refund_status"])
    cancel_payout_for_payment(payment)
    notify_refund_team(refund)
    return refund


@transaction.atomic
def reject_refund(refund: Refund, actor=None, note: str = "") -> bool:
    """Reject a pending refund request and resume an eligible owner payout."""
    refund = (
        Refund.objects.select_for_update()
        .select_related("payment", "booking", "booking__owner", "booking__renter")
        .filter(pk=refund.pk)
        .first()
    )
    if refund is None or refund.status != Refund.Status.PENDING:
        return False
    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    refund.status = Refund.Status.REJECTED
    refund.note = (
        (note or "").strip()[:255] or "Refund request rejected after review."
    )
    refund.save(update_fields=["status", "note"])
    payment.refund_status = Payment.RefundStatus.NONE
    payment.save(update_fields=["refund_status"])

    booking = refund.booking
    if booking.status not in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        payout = Payout.objects.filter(payment=payment).first()
        if payout and payout.status == Payout.Status.CANCELLED:
            payout.status = (
                Payout.Status.ELIGIBLE
                if payout.available_at <= timezone.now()
                else Payout.Status.SCHEDULED
            )
            payout.save(update_fields=["status", "updated_at"])
        elif payout is None:
            create_payout_for_payment(payment)

    for recipient in (booking.renter, booking.owner):
        notify(
            recipient,
            Notification.Kind.REFUND_REJECTED,
            "notif_refund_rejected",
            "notif_refund_rejected_body",
            params={"reference": refund.reference, "title": booking.property_title},
            link=payment.get_absolute_url(),
        )
    return True


@transaction.atomic
def process_refund(
    refund: Refund, actor=None, *, external: bool = False, note: str = ""
) -> bool:
    # Lock both rows so two owners/admins cannot process the same refund (or
    # two refunds for one payment) simultaneously.
    refund = (
        Refund.objects.select_for_update()
        .select_related("payment", "booking", "booking__owner")
        .filter(pk=refund.pk)
        .first()
    )
    if refund is None or refund.status != Refund.Status.PENDING:
        return False

    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    if payment.is_refunded:
        return False
    refund.payment = payment

    # Marking a real PayWay payment refunded without calling PayWay would
    # misrepresent the merchant's balance. The owner must first refund in the
    # PayWay portal, then explicitly record that external refund here.
    if not payment.can_refund_locally:
        if not external:
            raise RefundRequiresGateway(
                "Refunds for ABA PayWay payments must be issued in the PayWay merchant portal."
            )
        note = note or "Refunded via ABA PayWay merchant portal"
    if not refund.process(note=note):
        return False
    cancel_payout_for_payment(payment)
    booking = Booking.objects.select_for_update().get(pk=refund.booking_id)
    if booking.status not in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        booking.transition(BookingStatus.CANCELLED)
    notify(
        booking.renter,
        Notification.Kind.REFUND_PROCESSED,
        "notif_refund_processed",
        "notif_refund_processed_body",
        params={"amount": refund.amount_display, "title": booking.property_title},
        link=refund.payment.get_absolute_url(),
    )
    notify(
        booking.owner,
        Notification.Kind.REFUND_PROCESSED,
        "notif_refund_processed",
        "notif_refund_processed_body",
        params={"amount": refund.amount_display, "title": booking.property_title},
        link=refund.payment.get_absolute_url(),
    )
    return True


@transaction.atomic
def pay_out(payout: Payout, actor=None, note: str = "") -> bool:
    """Record a manual transfer of an eligible payout to the owner.

    This does not move money: the superadmin sends it through the bank and then
    records the transfer here so the owner sees the payout and the audit trail
    stores where it was sent.
    """
    payout = (
        Payout.objects.select_for_update()
        .select_related("owner", "payment", "payment__booking")
        .filter(pk=payout.pk)
        .first()
    )
    if payout is None or payout.status not in (
        Payout.Status.SCHEDULED,
        Payout.Status.ELIGIBLE,
    ):
        return False

    now = timezone.now()
    if payout.available_at > now:
        raise PayoutNotDue(f"The {hold_days()}-day hold period has not finished yet.")
    payment = payout.payment
    booking = payment.booking if payment.booking_id else None
    if (
        not payment.is_successful
        or payment.is_refunded
        or (
            booking is not None
            and booking.status in (BookingStatus.CANCELLED, BookingStatus.REJECTED)
        )
    ):
        raise PayoutBlocked("This payment was cancelled or refunded.")
    if payment.refunds.filter(status=Refund.Status.PENDING).exists():
        raise PayoutBlocked("A refund is still pending for this payment.")

    owner = payout.owner
    if not owner.has_payout_details:
        raise PayoutDetailsMissing("The owner has not added payout details yet.")

    payout.payout_method = owner.payout_method
    payout.payout_account_name = owner.payout_account_name
    payout.payout_account_number = owner.payout_account_number
    payout.payout_bank_name = owner.payout_bank_name
    payout.payout_phone = owner.payout_phone
    payout.status = Payout.Status.PAID
    payout.paid_at = now
    payout.recorded_by = actor
    payout.note = (note or "").strip()[:255]
    payout.save(
        update_fields=[
            "payout_method",
            "payout_account_name",
            "payout_account_number",
            "payout_bank_name",
            "payout_phone",
            "status",
            "paid_at",
            "recorded_by",
            "note",
            "updated_at",
        ]
    )
    notify(
        owner,
        Notification.Kind.PAYOUT_PAID,
        "notif_payout_paid",
        "notif_payout_paid_body",
        params={
            "amount": payout.amount_display,
            "title": payout.property_title,
        },
        link=f"/payments/{payout.payment_id}/",
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
        paid_at=booking.approved_at or timezone.now(),
    )
    booking.payment = payment
    booking.save(update_fields=["payment"])
    create_payout_for_payment(payment)
    return payment
