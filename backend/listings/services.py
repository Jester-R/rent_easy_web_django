from __future__ import annotations

from django.db import transaction

from bookings.models import ACTIVE_STATUSES, Booking
from listings.models import Property
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment, Refund
from payments.services import queue_refund


@transaction.atomic
def soft_delete_owner_property(property_id: int, owner) -> tuple[Property | None, int]:
    """Hide an owner's listing and queue admin review for active paid bookings."""
    prop = (
        Property.objects.select_for_update()
        .filter(pk=property_id, owner=owner)
        .first()
    )
    if prop is None:
        return None, 0
    if not prop.is_active:
        return prop, 0

    prop.is_active = False
    prop.save(update_fields=["is_active", "updated_at"])

    bookings = Booking.objects.filter(
        property_id=prop.pk,
        status__in=ACTIVE_STATUSES,
        payment__status=Payment.Status.SUCCESS,
    ).select_related("payment", "property", "renter", "owner")

    queued = 0
    for booking in bookings:
        payment = booking.payment
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
        elif payment.is_refunded or payment.refunds.filter(
            status=Refund.Status.PROCESSED
        ).exists():
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

    return prop, queued
