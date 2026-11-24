from __future__ import annotations

# NOTE: models that declare a ``property`` FK shadow the builtin inside the
# class body, so ``builtins.property`` is used explicitly for derived fields.
import builtins
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

ACTIVE_STATUSES = ("Pending", "Approved", "Confirmed")


def payment_window_hours() -> int:
    """Hours a renter has to pay a booking request before it expires."""
    return max(1, int(getattr(settings, "BOOKING_PAYMENT_WINDOW_HOURS", 5) or 5))


def rebook_cooldown_hours() -> int:
    """Hours before a renter may request the same property again."""
    return max(1, int(getattr(settings, "BOOKING_REBOOK_COOLDOWN_HOURS", 24) or 24))


#: Mirrors ``PropertyProvider._isValidStatusTransition`` from the Flutter app.
VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Pending": ("Approved", "Confirmed", "Rejected", "Cancelled", "Expired"),
    "Approved": ("Confirmed", "Cancelled", "Expired"),
    "Confirmed": ("Cancelled",),
    "Rejected": (),
    "Cancelled": (),
    "Expired": (),
}

TIMESTAMP_FIELD = {
    "Approved": "approved_at",
    "Rejected": "rejected_at",
    "Cancelled": "cancelled_at",
    "Expired": "expired_at",
}


class BookingStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    APPROVED = "Approved", "Approved"
    CONFIRMED = "Confirmed", "Confirmed"
    REJECTED = "Rejected", "Rejected"
    CANCELLED = "Cancelled", "Cancelled"
    EXPIRED = "Expired", "Expired"


class Booking(models.Model):
    property = models.ForeignKey(
        "listings.Property", on_delete=models.CASCADE, related_name="bookings"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="renters_bookings",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owners_bookings",
    )
    status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    move_in_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    lease_months = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True)
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["renter", "-created_at"]),
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} · {self.property_title}"

    # -- identity ------------------------------------------------------
    @builtins.property
    def reference(self) -> str:
        return f"BK-{self.pk:06d}" if self.pk else "BK-—"

    @builtins.property
    def property_title(self) -> str:
        return self.property.title if self.property_id else "—"

    @builtins.property
    def rent_display(self) -> str:
        return f"${float(self.monthly_rent or 0):,.0f}"

    # -- state machine --------------------------------------------------
    @builtins.property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @builtins.property
    def is_paid(self) -> bool:
        return bool(self.payment_id)

    @builtins.property
    def payment_deadline_at(self):
        return self.created_at + timedelta(hours=payment_window_hours())

    @builtins.property
    def payment_hours_remaining(self) -> float:
        if self.payment_id or self.status != BookingStatus.PENDING:
            return 0.0
        remaining = (self.payment_deadline_at - timezone.now()).total_seconds()
        return round(max(0.0, remaining / 3600), 2)

    @builtins.property
    def payout_status(self) -> str:
        payout = self._payout
        return payout.status if payout is not None else ""

    @builtins.property
    def payout_available_at(self):
        payout = self._payout
        return payout.available_at if payout is not None else None

    @builtins.property
    def refund(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("refunds")
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return self.refunds.order_by("-created_at").first()

    @builtins.property
    def refund_id(self) -> int | None:
        return self.refund.pk if self.refund else None

    @builtins.property
    def refund_status(self) -> str:
        return self.refund.status if self.refund else ""

    @builtins.property
    def refund_state(self) -> str:
        refund = self.refund
        if refund is None:
            return ""
        if refund.status == "Processed":
            return "Refunded"
        if refund.status == "Rejected":
            return "Refund failed"
        return "Refunding"

    @builtins.property
    def refund_conversation_id(self) -> int | None:
        return self.renter_refund_conversation_id or self.owner_refund_conversation_id

    @builtins.property
    def renter_refund_conversation_id(self) -> int | None:
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("refunds")
        if prefetched is not None:
            refund = prefetched[0] if prefetched else None
        else:
            refund = self.refunds.order_by("-created_at").first()
        return refund.renter_conversation_id if refund is not None else None

    @builtins.property
    def owner_refund_conversation_id(self) -> int | None:
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("refunds")
        if prefetched is not None:
            refund = prefetched[0] if prefetched else None
        else:
            refund = self.refunds.order_by("-created_at").first()
        return refund.owner_conversation_id if refund is not None else None

    @builtins.property
    def _payout(self):
        if not self.payment_id:
            return None
        return getattr(self.payment, "payout", None)

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.status, ())

    def can_cancel(self) -> bool:
        if self.status == BookingStatus.PENDING and not self.payment_id:
            return self.can_transition_to(BookingStatus.CANCELLED)
        if self.status not in (
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
        ):
            return False
        if not self.payment_id:
            return False
        if self.refund_state == "Refunding":
            return False
        paid_at = self.payment.paid_at or self.payment.created_at
        if timezone.now() >= paid_at + timedelta(days=7):
            return False
        return self.can_transition_to(BookingStatus.CANCELLED)

    def can_owner_cancel(self) -> bool:
        """Owners may only cancel bookings the renter has already paid for."""
        return bool(self.payment_id) and self.can_cancel()

    def get_absolute_url(self) -> str:
        """API path for the booking: owner-facing when the owner is the viewer."""
        user = getattr(self, "_viewer", None)
        if (
            user is not None
            and getattr(user, "is_owner", False)
            and self.owner_id == user.pk
        ):
            return f"/owner/bookings/{self.pk}/"
        return f"/rent/bookings/{self.pk}/"

    def transition(self, new_status: str) -> bool:
        """Apply a status transition, stamping the matching timestamp."""
        if not self.can_transition_to(new_status):
            return False
        self.status = new_status
        field = TIMESTAMP_FIELD.get(new_status)
        if field:
            setattr(self, field, timezone.now())
        self.save(update_fields=(["status"] + ([field] if field else [])))
        return True

    @builtins.property
    def resolved_timestamp(self):
        return {
            BookingStatus.APPROVED: self.approved_at,
            BookingStatus.REJECTED: self.rejected_at,
            BookingStatus.CANCELLED: self.cancelled_at,
            BookingStatus.EXPIRED: self.expired_at,
        }.get(self.status) or self.created_at
