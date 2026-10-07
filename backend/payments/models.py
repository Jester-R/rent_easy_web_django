from __future__ import annotations

# NOTE: models that declare a ``property`` FK shadow the builtin inside the
# class body, so ``builtins.property`` is used explicitly for derived fields.
import builtins
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "Success", "Success"
        FAILED = "Failed", "Failed"

    class RefundStatus(models.TextChoices):
        NONE = "None", "None"
        PENDING = "Pending", "Pending"
        PROCESSED = "Processed", "Processed"

    class Method(models.TextChoices):
        ABA = "ABA Pay (Mock)", "ABA Pay (Mock)"
        WING = "Wing (Mock)", "Wing (Mock)"
        CARD = "Credit Card (Mock)", "Credit Card (Mock)"

    reference = models.CharField(max_length=24, unique=True, editable=False)
    property = models.ForeignKey(
        "listings.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_records",
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    method = models.CharField(max_length=32, choices=Method.choices, default=Method.ABA)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.SUCCESS, db_index=True
    )
    refund_status = models.CharField(
        max_length=12, choices=RefundStatus.choices, default=RefundStatus.NONE
    )
    refunded_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    created_at = models.DateTimeField(default=timezone.now)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} · {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        super().save(*args, **kwargs)

    def _generate_reference(self) -> str:
        import uuid

        return f"PAY-{uuid.uuid4().hex[:12].upper()}"

    @builtins.property
    def amount_display(self) -> str:
        return f"${float(self.amount or 0):,.0f}"

    @builtins.property
    def refunded_display(self) -> str:
        return f"${float(self.refunded_amount or 0):,.0f}"

    @builtins.property
    def is_refunded(self) -> bool:
        return self.refund_status == self.RefundStatus.PROCESSED

    @builtins.property
    def is_successful(self) -> bool:
        return self.status == self.Status.SUCCESS

    def get_absolute_url(self) -> str:
        return f"/rent/payments/{self.pk}/"

    @builtins.property
    def property_title(self) -> str:
        if self.property_id:
            return self.property.title
        if self.booking_id:
            return self.booking.property_title
        return "—"

    def mark_refunded(self, amount: Decimal | None = None) -> None:
        value = Decimal(amount if amount is not None else (self.amount or 0))
        self.refund_status = self.RefundStatus.PROCESSED
        self.refunded_amount = value
        self.refunded_at = timezone.now()
        self.save(update_fields=["refund_status", "refunded_amount", "refunded_at"])


class Refund(models.Model):
    class Reason(models.TextChoices):
        CANCELLED_BY_RENTER = "cancelled_by_renter", "Cancelled by renter"
        REJECTED_BY_OWNER = "rejected_by_owner", "Rejected by owner"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PROCESSED = "Processed", "Processed"

    reference = models.CharField(max_length=24, unique=True, editable=False)
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="refunds"
    )
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.CASCADE, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(
        max_length=24, choices=Reason.choices, default=Reason.OTHER
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} · {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import uuid

            self.reference = f"RF-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @builtins.property
    def amount_display(self) -> str:
        return f"${float(self.amount or 0):,.0f}"

    def process(self, note: str = "") -> bool:
        if self.status == self.Status.PROCESSED:
            return False
        self.status = self.Status.PROCESSED
        self.processed_at = timezone.now()
        if note:
            self.note = note
        self.save(update_fields=["status", "processed_at", "note"])
        self.payment.mark_refunded(self.amount)
        return True
