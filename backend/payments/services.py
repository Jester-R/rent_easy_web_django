from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import PlatformSettings, Role, User
from bookings.models import ACTIVE_STATUSES, Booking, BookingStatus, payment_window_hours
from chat.models import Conversation
from notifications.models import Notification
from notifications.services import notify
from payments.gateways import aba as aba_gateway
from payments.gateways import stripe as stripe_gateway
from payments.models import Payment, Payout, Refund, RefundMessage

logger = logging.getLogger(__name__)


class UnsupportedPaymentMethod(RuntimeError):
    """Raised when a client asks for a payment method nobody provides."""

    code = "unsupported_method"


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


FREE_CANCELLATION_DAYS = 5
FINAL_CANCELLATION_DAYS = 7


def payment_started_at(payment: Payment):
    return payment.paid_at or payment.created_at or timezone.now()


def cancellation_fee(payment: Payment) -> tuple[Decimal, Decimal]:
    """Return the admin-set late cancellation fee, not the payment commission."""
    settings_row = PlatformSettings.objects.filter(pk=1).first()
    raw_amount = getattr(settings_row, "late_cancellation_fee", Decimal("0"))
    try:
        amount = Decimal(str(raw_amount or 0))
    except (AttributeError, TypeError, ValueError):
        amount = Decimal("0")
    if not amount.is_finite() or amount < 0:
        amount = Decimal("0")
    return Decimal("0"), amount.quantize(Decimal("0.01"))


def cancellation_commission(payment: Payment) -> tuple[Decimal, Decimal]:
    return cancellation_fee(payment)


def cancellation_terms(payment: Payment) -> tuple[bool, Decimal, Decimal, str]:
    """Return allowed, fee rate, fee due, and failure code."""
    elapsed = timezone.now() - payment_started_at(payment)
    if elapsed >= timedelta(days=FINAL_CANCELLATION_DAYS):
        return False, Decimal("0"), Decimal("0"), "cancellation_window_closed"
    if elapsed >= timedelta(days=FREE_CANCELLATION_DAYS):
        rate, amount = cancellation_fee(payment)
        return True, rate, amount, ""
    return True, Decimal("0"), Decimal("0"), ""


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
    "stripe": Payment.Method.STRIPE,
    "stripe card": Payment.Method.STRIPE,
    "stripe checkout": Payment.Method.STRIPE,
}


def normalize_method(value: str | None, default: str = Payment.Method.ABA) -> str:
    """Map a client-supplied payment method onto a canonical ``Method`` value."""
    if not value:
        return default
    normalized = _METHOD_ALIASES.get(str(value).strip().lower())
    if normalized is None:
        raise UnsupportedPaymentMethod(
            f"Unsupported payment method: {value!r}. "
            "ABA PayWay and Stripe Card are available."
        )
    return normalized


@dataclass
class PaymentResult:
    """Outcome of starting a booking payment.

    ``qr`` contains the PayWay generated image when payment is pending.
    """

    payment: Payment
    checkout: dict | None = None
    qr: dict | None = None


def _coerce_date(value):
    """Normalize ISO date strings (from JSON bodies) into ``date`` objects."""
    if isinstance(value, str):
        return parse_date(value.strip())
    return value


def _date_text(value) -> str:
    value = _coerce_date(value)
    return value.strftime("%d %b %Y") if value else "Not specified"


def _lease_text(booking: Booking) -> str:
    months = int(booking.lease_months or 1)
    label = f"{months} month{'s' if months != 1 else ''}"
    if booking.end_date:
        label += f" (until {_date_text(booking.end_date)})"
    return label


@transaction.atomic
def create_booking(
    *,
    property_obj,
    renter,
    move_in_date=None,
    end_date=None,
    lease_months: int = 1,
    note: str = "",
):
    """Create a pending booking request, guarding the active-booking rule."""
    from listings.models import Property

    move_in_date = _coerce_date(move_in_date)
    end_date = _coerce_date(end_date)

    expire_unpaid_bookings()
    Property.objects.select_for_update().get(pk=property_obj.pk)
    if has_active_booking(renter, property_obj):
        return None
    if Booking.objects.filter(
        renter=renter,
        property=property_obj,
        created_at__date=timezone.localdate(),
    ).exists():
        return None
    if Booking.objects.filter(
        property=property_obj,
        status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        payment_id__isnull=True,
    ).exists():
        return None
    if Booking.objects.filter(
        property=property_obj, status__in=ACTIVE_STATUSES
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
        params={
            "renter": renter.display_name,
            "title": property_obj.title,
            "amount": booking.rent_display,
            "move_in": _date_text(booking.move_in_date),
            "lease": _lease_text(booking),
            "reference": booking.reference,
            "note": booking.note or "No message",
        },
        link=booking.get_absolute_url(),
    )
    return booking


def has_active_booking(renter, property_obj) -> bool:
    """True when renter already booked this room today (1 room/renter/day)."""
    return Booking.objects.filter(
        renter=renter,
        property=property_obj,
        created_at__date=timezone.localdate(),
    ).exists()


def expire_unpaid_bookings() -> int:
    """Expire unpaid requests that passed the payment window.

    Expiry is refreshed on the booking/listing endpoints and can also be run
    from cron via ``manage.py expire_unpaid_bookings``. At most 500 rows are
    handled per call so a request never stalls on a large backlog.
    """
    cutoff = timezone.now() - timedelta(hours=payment_window_hours())
    candidates = (
        Booking.objects.filter(
            status=BookingStatus.PENDING,
            created_at__lt=cutoff,
            payment_id__isnull=True,
        )
        .select_related("property", "renter", "owner")
        .order_by("created_at")[:500]
    )
    expired = 0
    for candidate in candidates:
        with transaction.atomic():
            booking = (
                Booking.objects.select_for_update()
                .select_related("property", "renter", "owner")
                .filter(
                    pk=candidate.pk,
                    status=BookingStatus.PENDING,
                    payment_id__isnull=True,
                )
                .first()
            )
            if booking is None:
                continue
            ok, _code = transition_booking(booking, BookingStatus.EXPIRED)
            if not ok:
                continue
            expired += 1
            notify(
                booking.renter,
                Notification.Kind.BOOKING_UPDATE,
                "notif_booking_expired",
                "notif_booking_expired_body",
                params={
                    "title": booking.property_title,
                    "hours": payment_window_hours(),
                },
                link=booking.get_absolute_url(),
            )
    return expired

def payout_for_payment(payment: Payment | None) -> Payout | None:
    if payment is None or not payment.pk:
        return None
    return Payout.objects.filter(payment_id=payment.pk).first()


def cancellation_window_open(booking: Booking) -> bool:
    """Whether a paid booking may still be cancelled, counted from payment."""
    if not booking.payment_id:
        return True
    allowed, _, _, _ = cancellation_terms(booking.payment)
    return allowed


@transaction.atomic
def transition_booking(
    booking: Booking,
    new_status: str,
    actor=None,
    request_note: str | None = None,
    *,
    skip_refund: bool = False,
    skip_window: bool = False,
) -> tuple[bool, str]:
    """Apply a validated booking transition and notify both parties."""
    if (
        new_status == BookingStatus.CANCELLED
        and booking.payment_id
        and not skip_window
        and not cancellation_window_open(booking)
    ):
        return False, "cancellation_window_closed"
    if not booking.can_transition_to(new_status):
        return False, "invalid_transition"
    if (
        new_status == BookingStatus.CANCELLED
        and actor is not None
        and getattr(actor, "is_owner", False)
        and not booking.payment_id
    ):
        return False, "payment_required"

    if new_status == BookingStatus.CONFIRMED:
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

    if new_status == BookingStatus.CONFIRMED:
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
        if not skip_refund:
            queue_refund(
                booking, reason, actor=actor, request_note=request_note
            )
        from listings.services import reopen_property_if_idle

        reopen_property_if_idle(booking.property_id)

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
    """Start a booking payment through the gateway matching the method."""
    canonical = normalize_method(method)
    if canonical == Payment.Method.STRIPE:
        if not stripe_gateway.is_configured():
            raise stripe_gateway.StripeGatewayError(
                "not_configured", "Stripe is not configured"
            )
        return _start_stripe_payment(booking)
    if canonical != Payment.Method.ABA:
        raise UnsupportedPaymentMethod(
            f"Unsupported payment method: {method!r}. "
            "ABA PayWay and Stripe Card are available."
        )
    if not aba_gateway.is_configured():
        raise aba_gateway.PayWayError("not_configured", "ABA PayWay is not configured")
    return _start_aba_payment(booking)


@transaction.atomic
def _start_aba_payment(booking: Booking) -> PaymentResult:
    """Create a pending payment and request its PayWay QR image."""
    rent = Decimal(booking.monthly_rent).quantize(Decimal("0.01"))
    platform_settings = PlatformSettings.objects.filter(pk=1).first()
    rates = (platform_settings.commission_rates if platform_settings else {}) or {}
    try:
        commission_rate = Decimal(str(rates.get(Payment.Method.ABA, 0)))
    except AttributeError, TypeError, ValueError:
        commission_rate = Decimal("0")
    commission_rate = min(Decimal("100"), max(Decimal("0"), commission_rate))
    fee = (rent * commission_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total = rent + fee
    payment = Payment.objects.create(
        property=booking.property,
        user=booking.renter,
        booking=booking,
        amount=total,
        method=Payment.Method.ABA,
        status=Payment.Status.PENDING,
        provider=Payment.Provider.ABA_PAYWAY,
    )
    # The reference is generated in ``save``; use it as the PayWay tran_id so
    # the callback can find this row without trusting client input.
    payment.provider_ref = payment.reference
    payment.save(update_fields=["provider_ref"])

    renter = booking.renter
    firstname, lastname = _payway_name_parts(
        renter.payment_account_name or renter.display_name
    )
    items = [{"name": booking.property_title, "quantity": 1, "price": float(total)}]
    return_params = json.dumps({"payment_id": payment.pk}, separators=(",", ":"))

    try:
        qr = aba_gateway.create_qr_payment(
            tran_id=payment.provider_ref,
            amount=payment.amount,
            firstname=firstname,
            lastname=lastname,
            email=renter.email,
            phone=renter.payment_phone,
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
            "amount": aba_gateway.amount_to_string(payment.amount),
            "merchant_id": aba_gateway.merchant_id(),
            "tran_id": payment.provider_ref,
        },
        "commission": {
            "base_amount": str(rent),
            "rate": str(commission_rate),
            "amount": str(fee),
        },
    }
    payment.save(update_fields=["gateway_payload"])
    return PaymentResult(payment, qr=qr)


def _payway_name_parts(display_name: str) -> tuple[str, str]:
    """PayWay rejects names containing digits/special characters."""
    parts = [re.sub(r"[^A-Za-z]", "", part) for part in (display_name or "").split()]
    parts = [part for part in parts if part]
    firstname = parts[0] if parts else "RentEasy"
    lastname = parts[-1] if len(parts) > 1 else "Renter"
    return firstname[:100], lastname[:100]


@transaction.atomic
def _start_stripe_payment(booking: Booking) -> PaymentResult:
    """Create a pending payment and its hosted Stripe Checkout session."""
    rent = Decimal(booking.monthly_rent).quantize(Decimal("0.01"))
    platform_settings = PlatformSettings.objects.filter(pk=1).first()
    rates = (platform_settings.commission_rates if platform_settings else {}) or {}
    try:
        commission_rate = Decimal(str(rates.get(Payment.Method.STRIPE, 0)))
    except (AttributeError, TypeError, ValueError):
        commission_rate = Decimal("0")
    commission_rate = min(Decimal("100"), max(Decimal("0"), commission_rate))
    fee = (rent * commission_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total = rent + fee
    payment = Payment.objects.create(
        property=booking.property,
        user=booking.renter,
        booking=booking,
        amount=total,
        method=Payment.Method.STRIPE,
        status=Payment.Status.PENDING,
        provider=Payment.Provider.STRIPE,
    )

    renter = booking.renter
    try:
        session = stripe_gateway.create_checkout_session(
            client_reference_id=payment.reference,
            amount=payment.amount,
            description=booking.property_title,
            email=renter.email,
            payment_id=payment.pk,
        )
    except Exception as exc:
        payment.status = Payment.Status.FAILED
        payment.gateway_payload = {
            "error": str(exc),
            "code": getattr(exc, "code", ""),
        }
        payment.save(update_fields=["status", "gateway_payload"])
        raise

    # The checkout session id is the reconciliation handle used by the webhook
    # and the refresh endpoints; the reference stays the human-facing id.
    payment.provider_ref = session["id"]
    payment.gateway_payload = {
        "request": {
            "amount": str(total),
            "session_id": session["id"],
            "currency": session.get("currency") or settings.STRIPE_CURRENCY,
        },
        "commission": {
            "base_amount": str(rent),
            "rate": str(commission_rate),
            "amount": str(fee),
        },
        "stripe": {
            "session_id": session["id"],
            "payment_intent": "",
        },
    }
    payment.save(update_fields=["provider_ref", "gateway_payload"])
    return PaymentResult(payment, checkout={"provider": "stripe", "url": session["url"]})


def _attach_successful_payment(booking: Booking, payment: Payment) -> None:
    """Link a successful payment to its booking and alert both parties."""
    booking.payment = payment
    update_fields = ["payment"]
    if booking.status in (BookingStatus.PENDING, BookingStatus.APPROVED):
        booking.status = BookingStatus.CONFIRMED
        update_fields.append("status")
    booking.save(update_fields=update_fields)
    from listings.services import close_property_for_rent

    close_property_for_rent(booking.property_id)
    notify(
        booking.renter,
        Notification.Kind.PAYMENT_SUCCESS,
        "notif_payment_success",
        "notif_payment_success_body",
        params={
            "amount": payment.amount_display,
            "method": payment.method,
            "title": booking.property_title,
        },
        link=booking.get_absolute_url(),
    )
    payout = create_payout_for_payment(payment)
    if payout is None:
        return
    money = lambda amount: f"${Decimal(amount):,.2f}"
    notify(
        booking.owner,
        Notification.Kind.PAYMENT_RECEIVED,
        "notif_payment_received",
        "notif_payment_received_body",
        params={
            "renter": booking.renter.display_name,
            "amount": payment.amount_display,
            "commission": money(payout.commission_amount),
            "commission_rate": f"{payout.commission_rate:g}%",
            "payout_amount": money(payout.amount),
            "method": payment.method,
            "title": booking.property_title,
        },
        message_overrides={
            "body_en": "{renter} paid {amount} for {title} using {method}. Platform commission: {commission_rate} ({commission}). Your payout after the 7-day hold: {payout_amount}.",
            "body_km": "{renter} បានបង់ {amount} សម្រាប់ {title} តាមរយៈ {method}។ កម្រៃជើងសារវេទិកា៖ {commission_rate} ({commission})។ ប្រាក់ដែលអ្នកនឹងទទួលបានបន្ទាប់ពីរយៈពេលរង់ចាំ ៧ ថ្ងៃ៖ {payout_amount}។",
        },
        link=payment.get_absolute_url(),
    )


def _payout_snapshot(owner) -> dict[str, str]:
    account = owner.get_payout_account()
    return {
        "payout_method": owner.payout_method or "",
        "payout_account_name": account["account_name"],
        "payout_account_number": account["account_number"],
        "payout_bank_name": account["bank_name"],
        "payout_phone": account["phone"],
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
    platform_settings = PlatformSettings.objects.filter(pk=1).first()
    commission_rates = (
        platform_settings.commission_rates if platform_settings else {}
    ) or {}
    try:
        commission_rate = Decimal(str(commission_rates.get(payment.method, 0)))
    except AttributeError, TypeError, ValueError:
        commission_rate = Decimal("0")
    commission_rate = min(Decimal("100"), max(Decimal("0"), commission_rate))
    paid_at_for_rate = payment.paid_at or payment.created_at or timezone.now()
    if (
        platform_settings
        and platform_settings.commission_rates_updated_at
        and paid_at_for_rate < platform_settings.commission_rates_updated_at
    ):
        commission_rate = Decimal("0")
    commission_snapshot = (payment.gateway_payload or {}).get("commission") or {}
    if (
        payment.provider
        in (Payment.Provider.ABA_PAYWAY, Payment.Provider.STRIPE)
        and commission_snapshot
    ):
        commission_rate = Decimal(str(commission_snapshot.get("rate", commission_rate)))
        commission_amount = Decimal(
            str(commission_snapshot.get("amount", "0"))
        ).quantize(Decimal("0.01"))
        gross_amount = Decimal(payment.amount).quantize(Decimal("0.01"))
    else:
        gross_amount = Decimal(payment.amount).quantize(Decimal("0.01"))
        commission_amount = (gross_amount * commission_rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    net_amount = gross_amount - commission_amount
    payout, created = Payout.objects.get_or_create(
        payment=payment,
        defaults={
            "owner": owner,
            "amount": net_amount,
            "gross_amount": gross_amount,
            "commission_rate": commission_rate,
            "commission_amount": commission_amount,
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
        revised_gross = Decimal(payment.amount).quantize(Decimal("0.01"))
        commission_snapshot = (payment.gateway_payload or {}).get("commission") or {}
        revised_commission = (
            Decimal(str(commission_snapshot["amount"])).quantize(Decimal("0.01"))
            if commission_snapshot
            else (revised_gross * payout.commission_rate / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        revised_net = revised_gross - revised_commission
        if payout.gross_amount != revised_gross or payout.amount != revised_net:
            payout.gross_amount = revised_gross
            payout.commission_amount = revised_commission
            payout.amount = revised_net
            payout.save(
                update_fields=[
                    "gross_amount",
                    "commission_amount",
                    "amount",
                    "updated_at",
                ]
            )
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
    base.filter(
        payment__status__in=[Payment.Status.FAILED, Payment.Status.CANCELLED]
    ).update(**cancelled)
    base.filter(payment__refund_status=Payment.RefundStatus.PROCESSED).update(
        **cancelled
    )
    base.filter(
        payment__refunds__status__in=(
            Refund.Status.ACCEPTED,
            Refund.Status.PROCESSED,
        )
    ).update(**cancelled)
    base.filter(
        payment__booking__status__in=[
            BookingStatus.CANCELLED,
            BookingStatus.REJECTED,
            BookingStatus.EXPIRED,
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


def cancel_competing_payments(payment: Payment) -> int:
    """Cancel other pending payment attempts once one method succeeded."""
    if not payment.booking_id:
        return 0
    return Payment.objects.filter(
        booking_id=payment.booking_id,
        status=Payment.Status.PENDING,
    ).exclude(pk=payment.pk).update(status=Payment.Status.CANCELLED)


def _fail_late_payment(payment: Payment, payload: dict, error: str, note: str) -> None:
    """Mark an unusable gateway payment failed and queue its refund."""
    payment.status = Payment.Status.FAILED
    needs_refund = not payment.is_refunded
    if needs_refund:
        payment.refund_status = Payment.RefundStatus.PENDING
    payment.gateway_payload = {**payment.gateway_payload, **payload, "error": error}
    payment.save(update_fields=["status", "refund_status", "gateway_payload"])
    if needs_refund and not Refund.objects.filter(
        payment=payment, status=Refund.Status.PENDING
    ).exists():
        Refund.objects.create(
            payment=payment,
            booking_id=payment.booking_id,
            amount=payment.amount,
            reason=Refund.Reason.OTHER,
            note=note,
        )


def _booking_conflict_or_attach(payment: Payment, payload: dict) -> bool:
    """Finalize a successful gateway payment against its booking.

    Shared by the ABA PayWay and Stripe confirm paths. Returns ``False`` when
    the payment row must stay unlinked: a missing booking, or a duplicate
    charge for a booking that another transaction already paid. The duplicate
    case queues a refund because the money has really moved.
    """
    booking = (
        Booking.objects.select_for_update()
        .select_related("property", "renter", "owner")
        .filter(pk=payment.booking_id)
        .first()
    )
    if booking is None:
        return False
    if booking.status in (
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ):
        _fail_late_payment(
            payment,
            payload,
            "booking_closed",
            "Payment received after the booking was cancelled or expired.",
        )
        return False
    if booking.payment_id and booking.payment_id != payment.pk:
        _fail_late_payment(
            payment,
            payload,
            "booking_already_paid",
            "Duplicate payment for an already-paid booking.",
        )
        return False

    payment.status = Payment.Status.SUCCESS
    payment.paid_at = payment.paid_at or timezone.now()
    payment.gateway_payload = {**payment.gateway_payload, **payload}
    payment.save(update_fields=["status", "paid_at", "gateway_payload"])
    cancel_competing_payments(payment)
    if not booking.payment_id:
        _attach_successful_payment(booking, payment)
    return True


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

    return _booking_conflict_or_attach(payment, payload)


def reconcile_aba_payment(payment: Payment) -> bool:
    """Ask PayWay for the authoritative status and apply it."""
    if payment.provider != Payment.Provider.ABA_PAYWAY or not payment.provider_ref:
        return False
    gateway_payload = (
        payment.gateway_payload if isinstance(payment.gateway_payload, dict) else {}
    )
    request_payload = (
        gateway_payload.get("request")
        if isinstance(gateway_payload.get("request"), dict)
        else {}
    )
    data = aba_gateway.check_transaction(
        payment.provider_ref,
        merchant_id_override=request_payload.get("merchant_id"),
    )
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
def confirm_stripe_payment(
    payment_id: int, *, session: dict, payload: dict | None = None
) -> bool:
    """Reconcile a Stripe Checkout session with a pending payment row.

    Idempotent: a second webhook or refresh returns ``True`` without creating
    another notification. An amount mismatch or a booking that already has a
    different payment marks this payment failed instead of double-paying.
    """
    payment = (
        Payment.objects.select_for_update()
        .select_related("booking", "booking__renter", "booking__owner", "property")
        .filter(pk=payment_id)
        .first()
    )
    if payment is None or payment.provider != Payment.Provider.STRIPE:
        return False
    if payment.is_successful:
        return True

    payload = payload or {}
    payment_status = str(session.get("payment_status") or "")
    session_status = str(session.get("status") or "")

    # A session that expired without payment can never complete.
    if stripe_gateway.session_is_expired(session_status):
        payment.status = Payment.Status.FAILED
        payment.gateway_payload = {
            **payment.gateway_payload,
            **payload,
            "session": session,
            "error": "session_expired",
        }
        payment.save(update_fields=["status", "gateway_payload"])
        return False

    if not stripe_gateway.session_is_paid(payment_status):
        # Still open and unpaid: leave the row pending for the next poll.
        return False

    amount_total = session.get("amount_total")
    if amount_total is not None:
        try:
            paid_minor = Decimal(str(amount_total))
        except Exception:
            paid_minor = None
        expected_minor = Decimal(
            stripe_gateway.amount_to_minor_units(payment.amount)
        )
        if paid_minor is None or paid_minor != expected_minor:
            payment.status = Payment.Status.FAILED
            payment.gateway_payload = {
                **payment.gateway_payload,
                **payload,
                "session": session,
                "error": "amount_mismatch",
                "paid_amount": str(amount_total),
            }
            payment.save(update_fields=["status", "gateway_payload"])
            return False

    stripe_info = {
        "session_id": session.get("id") or payment.provider_ref,
        "payment_intent": str(session.get("payment_intent") or ""),
    }
    return _booking_conflict_or_attach(payment, {**payload, "stripe": stripe_info})


def reconcile_stripe_payment(payment: Payment) -> bool:
    """Ask Stripe for the authoritative session status and apply it."""
    if payment.provider != Payment.Provider.STRIPE or not payment.provider_ref:
        return False
    session = stripe_gateway.retrieve_checkout_session(payment.provider_ref)
    return confirm_stripe_payment(
        payment.pk, session=session, payload={"checkout_session": session}
    )


def _session_from_event_object(obj) -> dict:
    """Project a Stripe SDK session object onto the plain session dict shape."""
    payment_intent = getattr(obj, "payment_intent", "")
    if payment_intent is not None and not isinstance(payment_intent, str):
        payment_intent = getattr(payment_intent, "id", "") or ""
    return {
        "id": getattr(obj, "id", "") or "",
        "status": getattr(obj, "status", "") or "",
        "payment_status": getattr(obj, "payment_status", "") or "",
        "amount_total": getattr(obj, "amount_total", None),
        "currency": getattr(obj, "currency", "") or "",
        "payment_intent": payment_intent or "",
        "client_reference_id": getattr(obj, "client_reference_id", "") or "",
        "metadata": stripe_gateway.plain_dict(getattr(obj, "metadata", None)),
    }


@transaction.atomic
def apply_stripe_event(event) -> bool:
    """Apply a signature-verified Stripe webhook event to its payment.

    ``checkout.session.completed`` (and the async success variant) confirm the
    payment; ``async_payment_failed``/``expired`` mark it failed. The session id
    stored in ``provider_ref`` is the lookup key, with the ``payment_id``
    metadata kept as a cross-check so an event for another session cannot
    retarget this row.
    """
    event_type = str(getattr(event, "type", "") or "")
    if event_type not in (
        stripe_gateway.COMPLETED_EVENTS | stripe_gateway.FAILED_EVENTS
    ):
        return False
    data = getattr(event, "data", None)
    obj = getattr(data, "object", None) if data is not None else None
    if obj is None:
        return False
    session = _session_from_event_object(obj)
    session_id = session["id"]
    if not session_id:
        return False

    payment = (
        Payment.objects.select_related("booking")
        .filter(provider=Payment.Provider.STRIPE, provider_ref=session_id)
        .first()
    )
    if payment is None:
        meta = session.get("metadata") or {}
        try:
            payment_id = int(meta.get("payment_id", ""))
        except (TypeError, ValueError):
            return False
        payment = (
            Payment.objects.select_related("booking")
            .filter(pk=payment_id, provider=Payment.Provider.STRIPE)
            .first()
        )
        if payment is None or payment.provider_ref != session_id:
            # The event does not belong to the row it claims: ignore it.
            return False

    if event_type in stripe_gateway.FAILED_EVENTS:
        if payment.is_pending:
            payment.status = Payment.Status.FAILED
            payment.gateway_payload = {
                **payment.gateway_payload,
                "event": event_type,
                "session": session,
                "error": "session_failed",
            }
            payment.save(update_fields=["status", "gateway_payload"])
        return False

    return confirm_stripe_payment(
        payment.pk, session=session, payload={"event": event_type}
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
        gateway_payload = (
            payment.gateway_payload if isinstance(payment.gateway_payload, dict) else {}
        )
        request_payload = (
            gateway_payload.get("request")
            if isinstance(gateway_payload.get("request"), dict)
            else {}
        )
        data = aba_gateway.check_transaction(
            tran_id,
            merchant_id_override=request_payload.get("merchant_id"),
        )
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


def _refund_chat_link(refund: Refund) -> str:
    payment_link = refund.payment.get_absolute_url()
    return payment_link if payment_link else "/console/payments/refunds"


def refund_support_admin():
    return (
        User.objects.filter(is_active=True)
        .filter(Q(role=Role.SUPERADMIN) | Q(is_staff=True) | Q(is_superuser=True))
        .order_by("pk")
        .first()
    )


def ensure_refund_chat(
    refund: Refund, *, party: str, admin=None
) -> Conversation:
    """Create/open the one-to-one refund support chat for renter or owner."""
    if party not in ("renter", "owner"):
        raise RefundRequestError("invalid_refund_party")
    if refund.status not in (Refund.Status.ACCEPTED, Refund.Status.PROCESSED):
        raise RefundRequestError("refund_not_accepted")
    booking = refund.booking
    prop = refund.payment.property if refund.payment.property_id else booking.property
    support_admin = admin or refund_support_admin()
    participant_id = (
        booking.renter_id if party == "renter" else booking.owner_id
    )
    conversation, _created = Conversation.objects.get_or_create(
        refund=refund,
        refund_party=party,
        defaults={
            "property_id": prop.pk,
            "renter_id": booking.renter_id,
            "owner_id": booking.owner_id,
            "refund_participant_id": participant_id,
            "support_admin_id": support_admin.pk if support_admin else None,
        },
    )
    return conversation


def notify_refund_team(refund: Refund) -> None:
    """Notify active administrators that a refund needs review."""
    booking = refund.booking
    admins = (
        User.objects.filter(is_active=True)
        .filter(Q(role=Role.SUPERADMIN) | Q(is_staff=True) | Q(is_superuser=True))
        .distinct()
    )
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
            link="/console/payments/refunds",
            action="refund_review",
        )


@transaction.atomic
def request_refund(
    payment: Payment, requester, reason: str, request_note: str
) -> Refund:
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
        booking.owner_id
        if booking is not None
        else payment.property.owner_id
        if payment.property_id
        else None
    )
    allowed = (requester.is_renter and payment.user_id == requester.pk) or (
        requester.is_owner and owner_id == requester.pk
    )
    if not allowed:
        raise RefundRequestError("not_authorized")
    if booking is None:
        raise RefundRequestError("booking_required")
    allowed, commission_rate, commission_due, code = cancellation_terms(payment)
    if not allowed:
        raise RefundRequestError(code)
    if payment.refunds.filter(
        status__in=(Refund.Status.PENDING, Refund.Status.ACCEPTED)
    ).exists():
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
        commission_rate=commission_rate,
        commission_due=commission_due,
    )
    payment.refund_status = Payment.RefundStatus.PENDING
    payment.save(update_fields=["refund_status"])
    cancel_payout_for_payment(payment)
    notify_refund_team(refund)
    notify_cancellation_requested(refund, requester)
    return refund


@transaction.atomic
def request_booking_cancellation(
    booking: Booking, requester, message: str
) -> tuple[Refund | None, str]:
    """Create a refund request without cancelling the booking itself."""
    payment = booking.payment
    if payment is None or not payment.is_successful:
        if not requester.is_renter:
            return None, "payment_required"
        ok, code = transition_booking(
            booking,
            BookingStatus.CANCELLED,
            actor=requester,
            request_note=message,
        )
        return None, ("" if ok else code)
    reason = (
        Refund.Reason.CANCELLED_BY_OWNER
        if requester.is_owner
        else Refund.Reason.CANCELLED_BY_RENTER
    )
    try:
        refund = request_refund(payment, requester, reason, message)
    except RefundRequestError as exc:
        return None, exc.code
    return refund, ""


def notify_cancellation_requested(refund: Refund, requester) -> None:
    recipient = refund.booking.owner if requester.is_renter else refund.booking.renter
    notify(
        recipient,
        Notification.Kind.BOOKING_UPDATE,
        "notif_cancellation_requested",
        "notif_cancellation_requested_body",
        params={
            "amount": refund.amount_display,
            "title": refund.booking.property_title,
            "reference": refund.reference,
        },
        link=_refund_chat_link(refund),
        action="refund_review",
    )


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
    refund.note = (note or "").strip()[:255] or "Refund request rejected after review."
    refund.save(update_fields=["status", "note"])
    payment.refund_status = Payment.RefundStatus.NONE
    payment.save(update_fields=["refund_status"])

    booking = refund.booking
    if booking.status not in (
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ):
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
def accept_refund(
    refund: Refund, actor=None, *, note: str = "", commission_paid: bool = False
) -> bool:
    """Accept a refund request without cancelling a paid booking."""
    refund = (
        Refund.objects.select_for_update()
        .select_related("payment", "booking")
        .filter(pk=refund.pk)
        .first()
    )
    if refund is None or refund.status != Refund.Status.PENDING:
        return False
    if refund.commission_due > 0 and not refund.commission_paid and not commission_paid:
        raise RefundRequestError("cancellation_fee_required")

    booking = Booking.objects.select_for_update().get(pk=refund.booking_id)
    if commission_paid and refund.commission_due > 0:
        refund.mark_commission_paid()
    refund.status = Refund.Status.ACCEPTED
    refund.accepted_at = timezone.now()
    refund.accepted_by = actor
    if note:
        refund.note = note[:255]
    refund.save(
        update_fields=["status", "accepted_at", "accepted_by", "note"]
    )

    from listings.services import reopen_property_if_idle

    reopen_property_if_idle(booking.property_id)
    for recipient in (booking.renter, booking.owner):
        notify(
            recipient,
            Notification.Kind.BOOKING_UPDATE,
            "notif_refund_accepted",
            "notif_refund_accepted_body",
            params={
                "amount": refund.amount_display,
                "title": booking.property_title,
                "reference": refund.reference,
            },
            link=booking.get_absolute_url(),
        )
    return True


@transaction.atomic
def mark_refund_commission_paid(refund: Refund, actor=None) -> bool:
    """Record that the renter paid the separately charged cancellation fee."""
    refund = Refund.objects.select_for_update().filter(pk=refund.pk).first()
    if refund is None or refund.commission_due <= 0:
        return False
    if refund.status not in (Refund.Status.PENDING, Refund.Status.ACCEPTED):
        return False
    refund.mark_commission_paid()
    return True


@transaction.atomic
def add_refund_message(refund: Refund, sender, body: str) -> RefundMessage:
    """Add a message to a refund request for admin/renter/owner coordination."""
    refund = (
        Refund.objects.select_for_update()
        .select_related("booking", "booking__owner", "booking__renter")
        .get(pk=refund.pk)
    )
    body = (body or "").strip()
    if not body:
        raise RefundRequestError("refund_message_required")

    is_admin = (
        getattr(sender, "is_staff", False)
        or getattr(sender, "is_superuser", False)
        or getattr(sender, "role", "") == "superadmin"
    )
    allowed = is_admin or sender.pk in (
        refund.booking.owner_id,
        refund.booking.renter_id,
    )
    if not allowed:
        raise RefundRequestError("not_authorized")
    if is_admin and refund.status not in (
        Refund.Status.ACCEPTED,
        Refund.Status.PROCESSED,
    ):
        raise RefundRequestError("refund_not_accepted")

    message = RefundMessage.objects.create(
        refund=refund, sender=sender, body=body[:5000]
    )
    if is_admin:
        recipients = (refund.booking.renter, refund.booking.owner)
    else:
        recipients = User.objects.filter(is_active=True).filter(
            Q(role=Role.SUPERADMIN) | Q(is_staff=True) | Q(is_superuser=True)
        )
    for recipient in recipients:
        notify(
            recipient,
            Notification.Kind.CHAT_MESSAGE,
            "notif_refund_message",
            "notif_refund_message_body",
            params={
                "reference": refund.reference,
                "title": refund.booking.property_title,
                "sender": sender.display_name,
            },
            link=_refund_chat_link(refund),
            action="refund_message",
        )
    return message


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
    if refund is None:
        return False
    if refund.status == Refund.Status.PENDING and refund.requested_by_id is not None:
        return False
    if refund.status not in (Refund.Status.ACCEPTED, Refund.Status.PENDING):
        return False

    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    if payment.is_refunded:
        return False
    refund.payment = payment

    # Marking a real PayWay payment refunded without calling PayWay would
    # misrepresent the merchant's balance. The owner must first refund in the
    # PayWay portal, then explicitly record that external refund here. Stripe
    # payments are refunded through the Stripe Refund API automatically.
    if not payment.can_refund_locally:
        if not external:
            raise RefundRequiresGateway(
                "Refunds for ABA PayWay payments must be issued in the PayWay merchant portal."
            )
        note = note or "Refunded via ABA PayWay merchant portal"
    elif payment.provider == Payment.Provider.STRIPE:
        gateway_payload = (
            payment.gateway_payload if isinstance(payment.gateway_payload, dict) else {}
        )
        stripe_info = (
            gateway_payload.get("stripe")
            if isinstance(gateway_payload.get("stripe"), dict)
            else {}
        )
        payment_intent = str(stripe_info.get("payment_intent") or "")
        if not payment_intent:
            raise RefundRequiresGateway(
                "The Stripe payment intent is unknown, so the refund must be issued in the Stripe dashboard."
            )
        result = stripe_gateway.create_refund(
            payment_intent=payment_intent, amount=refund.amount
        )
        note = note or f"Refunded via Stripe ({result.get('status', 'succeeded')})"
    if not refund.process(note=note):
        return False
    cancel_payout_for_payment(payment)
    booking = Booking.objects.select_for_update().get(pk=refund.booking_id)
    from listings.services import reopen_property_if_idle

    if booking.status not in (
        BookingStatus.CANCELLED,
        BookingStatus.REJECTED,
        BookingStatus.EXPIRED,
    ):
        booking.transition(BookingStatus.CANCELLED)
    reopen_property_if_idle(booking.property_id)
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
            and booking.status
            in (BookingStatus.CANCELLED, BookingStatus.REJECTED, BookingStatus.EXPIRED)
        )
    ):
        raise PayoutBlocked("This payment was cancelled or refunded.")
    if payment.refunds.filter(
        status__in=(Refund.Status.PENDING, Refund.Status.ACCEPTED)
    ).exists():
        raise PayoutBlocked("A refund is still pending for this payment.")

    owner = payout.owner
    if not owner.has_payout_details:
        raise PayoutDetailsMissing("The owner has not added payout details yet.")

    payout.payout_method = owner.payout_method
    payout_account = owner.get_payout_account()
    payout.payout_account_name = payout_account["account_name"]
    payout.payout_account_number = payout_account["account_number"]
    payout.payout_bank_name = payout_account["bank_name"]
    payout.payout_phone = payout_account["phone"]
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
            "gross_amount": f"${payout.gross_amount:,.2f}",
            "commission": f"${payout.commission_amount:,.2f}",
            "commission_rate": f"{payout.commission_rate:g}%",
            "method": payout.payment_method,
            "title": payout.property_title,
        },
        message_overrides={
            "body_en": "{gross_amount} for {title} was paid using {method}. Platform commission: {commission_rate} ({commission}). Your payout of {amount} was sent to your account.",
            "body_km": "ប្រាក់សរុប {gross_amount} សម្រាប់ {title} បានទូទាត់តាម {method}។ កម្រៃជើងសារវេទិកា៖ {commission_rate} ({commission})។ ប្រាក់ផ្ទេរចំនួន {amount} ត្រូវបានផ្ញើទៅគណនីរបស់អ្នក។",
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
    cancel_competing_payments(payment)
    booking.payment = payment
    update_fields = ["payment"]
    if booking.status in (BookingStatus.PENDING, BookingStatus.APPROVED):
        booking.status = BookingStatus.CONFIRMED
        update_fields.append("status")
    booking.save(update_fields=update_fields)
    from listings.services import close_property_for_rent

    close_property_for_rent(booking.property_id)
    create_payout_for_payment(payment)
    return payment
