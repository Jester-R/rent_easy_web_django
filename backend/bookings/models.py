from __future__ import annotations

# NOTE: models that declare a ``property`` FK shadow the builtin inside the
# class body, so ``builtins.property`` is used explicitly for derived fields.
import builtins

from django.conf import settings
from django.db import models
from django.utils import timezone

ACTIVE_STATUSES = ("Pending", "Approved")

#: Mirrors ``PropertyProvider._isValidStatusTransition`` from the Flutter app.
VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Pending": ("Approved", "Rejected", "Cancelled"),
    "Approved": (),
    "Rejected": (),
    "Cancelled": (),
}

TIMESTAMP_FIELD = {
    "Approved": "approved_at",
    "Rejected": "rejected_at",
    "Cancelled": "cancelled_at",
}


class BookingStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    APPROVED = "Approved", "Approved"
    REJECTED = "Rejected", "Rejected"
    CANCELLED = "Cancelled", "Cancelled"


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
    lease_months = models.PositiveSmallIntegerField(default=12)
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

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.status, ())

    def can_cancel(self) -> bool:
        return self.can_transition_to(BookingStatus.CANCELLED)

    def can_approve(self) -> bool:
        return self.can_transition_to(BookingStatus.APPROVED)

    def can_reject(self) -> bool:
        return self.can_transition_to(BookingStatus.REJECTED)

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
        }.get(self.status) or self.created_at
