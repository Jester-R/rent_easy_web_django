from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from bookings.models import ACTIVE_STATUSES, Booking, BookingStatus
from listings.models import (
    OwnerPropertyAction,
    Property,
    PropertyOwnerStatus,
    active_paid_property_ids,
)
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment, Refund
from payments.services import queue_refund


OWNER_ACTION_LIMIT = 5
OWNER_ACTION_WINDOW = timedelta(hours=1)


class OwnerActionRateLimited(RuntimeError):
    code = "owner_action_rate_limited"


class OwnerActionBlocked(RuntimeError):
    code = "active_paid_booking"


def _reject_unpaid_bookings(property_id: int) -> int:
    rejected = 0
    bookings = (
        Booking.objects.select_for_update()
        .select_related("payment", "property", "renter")
        .filter(
            property_id=property_id,
            status__in=(BookingStatus.PENDING, BookingStatus.APPROVED),
        )
        .filter(Q(payment__isnull=True) | ~Q(payment__status=Payment.Status.SUCCESS))
    )
    for booking in bookings:
        if booking.payment_id and booking.payment.status == Payment.Status.PENDING:
            booking.payment.status = Payment.Status.CANCELLED
            booking.payment.save(update_fields=["status"])
            booking.payment = None
            booking.save(update_fields=["payment"])
        if not booking.transition(BookingStatus.REJECTED):
            continue
        rejected += 1
        notify(
            booking.renter,
            Notification.Kind.BOOKING_UPDATE,
            "notif_booking_update",
            "notif_booking_update_body",
            params={"title": booking.property_title, "status": "Rejected"},
            link=booking.get_absolute_url(),
        )
    return rejected


def _check_owner_action_limit(owner) -> None:
    since = timezone.now() - OWNER_ACTION_WINDOW
    used = OwnerPropertyAction.objects.filter(
        owner=owner,
        action__in=(
            OwnerPropertyAction.Action.UNAVAILABLE,
            OwnerPropertyAction.Action.REMOVE,
        ),
        created_at__gte=since,
    ).count()
    if used >= OWNER_ACTION_LIMIT:
        raise OwnerActionRateLimited()


@transaction.atomic
def set_owner_property_availability(
    property_id: int, owner, unavailable: bool
) -> tuple[Property | None, bool]:
    """Temporarily hide/show an owner's listing without deleting its data."""
    prop = (
        Property.objects.select_for_update().filter(pk=property_id, owner=owner).first()
    )
    if prop is None:
        return None, False
    if prop.owner_status == PropertyOwnerStatus.REMOVED:
        return prop, False
    if unavailable:
        if not prop.is_active:
            return prop, False
        _check_owner_action_limit(owner)
        prop.is_active = False
        prop.owner_status = PropertyOwnerStatus.UNAVAILABLE
        action = OwnerPropertyAction.Action.UNAVAILABLE
    else:
        if active_paid_property_ids([prop.pk]).exists():
            raise OwnerActionBlocked()
        released = _reject_unpaid_bookings(prop.pk)
        if prop.is_active and prop.owner_status == PropertyOwnerStatus.AVAILABLE and not released:
            return prop, False
        prop.is_active = True
        prop.rental_closed_at = None
        prop.owner_status = PropertyOwnerStatus.AVAILABLE
        action = None
    prop.save(
        update_fields=["is_active", "rental_closed_at", "owner_status", "updated_at"]
    )
    if action is not None:
        OwnerPropertyAction.objects.create(
            owner=owner, property=prop, action=action
        )
        _reject_unpaid_bookings(prop.pk)
    return prop, True


@transaction.atomic
def soft_delete_owner_property(property_id: int, owner) -> tuple[Property | None, int]:
    """Hide an owner's listing and queue admin review for active paid bookings."""
    prop = (
        Property.objects.select_for_update().filter(pk=property_id, owner=owner).first()
    )
    if prop is None:
        return None, 0
    if not prop.is_active:
        return prop, 0
    _check_owner_action_limit(owner)

    prop.is_active = False
    prop.owner_status = PropertyOwnerStatus.REMOVED
    prop.save(update_fields=["is_active", "owner_status", "updated_at"])
    OwnerPropertyAction.objects.create(
        owner=owner,
        property=prop,
        action=OwnerPropertyAction.Action.REMOVE,
    )

    bookings = Booking.objects.filter(
        property_id=prop.pk,
        status__in=ACTIVE_STATUSES,
        payment__status=Payment.Status.SUCCESS,
    ).select_related("payment", "property", "renter", "owner")

    queued = 0
    for booking in bookings:
        payment = booking.payment
        paid_at = payment.paid_at or payment.created_at
        if timezone.now() >= paid_at + timedelta(days=7):
            continue
        removal_note = (
            f"Owner removed property '{prop.title}' from public listings. "
            "Please review the property and booking before deciding whether to refund the renter."
        )
        pending_refund = payment.refunds.filter(status=Refund.Status.PENDING).first()
        if pending_refund is not None:
            if removal_note not in pending_refund.request_note:
                pending_refund.request_note = (
                    f"{pending_refund.request_note.strip()}\n\n{removal_note}".strip()
                )[:5000]
                pending_refund.save(update_fields=["request_note"])
            refund = pending_refund
        elif (
            payment.is_refunded
            or payment.refunds.filter(status=Refund.Status.PROCESSED).exists()
        ):
            continue
        else:
            refund = queue_refund(
                booking,
                Refund.Reason.CANCELLED_BY_OWNER,
                actor=owner,
                request_note=removal_note,
            )
            if refund is None:
                continue
        queued += 1
        notify(
            booking.renter,
            Notification.Kind.REFUND_REQUESTED,
            "notif_refund_requested",
            "notif_refund_requested_body",
            params={
                "amount": refund.amount_display,
                "title": booking.property_title,
                "reference": refund.reference,
            },
            link=payment.get_absolute_url(),
        )

    _reject_unpaid_bookings(prop.pk)
    return prop, queued


def _has_active_paid_booking(property_id: int) -> bool:
    return active_paid_property_ids([property_id]).exists()


@transaction.atomic
def close_property_for_rent(property_id: int) -> None:
    prop = Property.objects.select_for_update().filter(pk=property_id).first()
    if prop is None or not prop.is_active:
        return
    prop.is_active = False
    prop.rental_closed_at = timezone.now()
    prop.owner_status = PropertyOwnerStatus.UNAVAILABLE
    prop.save(
        update_fields=[
            "is_active",
            "rental_closed_at",
            "owner_status",
            "updated_at",
        ]
    )
    _reject_unpaid_bookings(prop.pk)


@transaction.atomic
def reopen_property_if_idle(property_id: int) -> bool:
    prop = Property.objects.select_for_update().filter(pk=property_id).first()
    if prop is None or prop.is_active or not prop.rental_closed_at:
        return False
    if prop.owner_status == PropertyOwnerStatus.REMOVED:
        return False
    if _has_active_paid_booking(property_id):
        return False
    prop.is_active = True
    prop.rental_closed_at = None
    prop.owner_status = PropertyOwnerStatus.AVAILABLE
    prop.save(
        update_fields=[
            "is_active",
            "rental_closed_at",
            "owner_status",
            "updated_at",
        ]
    )
    return True


@transaction.atomic
def reopen_owner_property(property_id: int, owner) -> tuple[Property | None, bool]:
    prop = (
        Property.objects.select_for_update().filter(pk=property_id, owner=owner).first()
    )
    if prop is None or prop.is_active or not prop.rental_closed_at:
        return prop, False
    if prop.owner_status == PropertyOwnerStatus.REMOVED:
        return prop, False
    if _has_active_paid_booking(property_id):
        return prop, False
    prop.is_active = True
    prop.rental_closed_at = None
    prop.owner_status = PropertyOwnerStatus.AVAILABLE
    prop.save(
        update_fields=[
            "is_active",
            "rental_closed_at",
            "owner_status",
            "updated_at",
        ]
    )
    return prop, True
