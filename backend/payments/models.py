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
        PENDING = "Pending", "Pending"
        SUCCESS = "Success", "Success"
        FAILED = "Failed", "Failed"

    class RefundStatus(models.TextChoices):
        NONE = "None", "None"
        PENDING = "Pending", "Pending"
        PROCESSED = "Processed", "Processed"

    class Method(models.TextChoices):
        ABA = "ABA Pay", "ABA Pay"
        ABA_MOCK = "ABA Pay (Mock)", "ABA Pay (Mock)"
        WING = "Wing (Mock)", "Wing (Mock)"
        CARD = "Credit Card (Mock)", "Credit Card (Mock)"

    class Provider(models.TextChoices):
        MOCK = "mock", "Mock gateway"
        ABA_PAYWAY = "aba_payway", "ABA PayWay"

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
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.MOCK
    )
    provider_ref = models.CharField(max_length=64, blank=True, db_index=True)
    gateway_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
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

    @builtins.property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    @builtins.property
    def can_refund_locally(self) -> bool:
        """Mock payments can be refunded in-app; real PayWay money must be
        refunded through the PayWay merchant portal (or its Refund API)."""
        return self.provider != self.Provider.ABA_PAYWAY

    def get_absolute_url(self) -> str:
        return f"/payments/{self.pk}/"

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


class Payout(models.Model):
    """Rent collected on behalf of an owner, released after the hold period.

    The platform receives the renter's payment; until ``available_at`` either
    side may cancel (which queues a refund and cancels this row). Once due, a
    superadmin transfers the money to the owner's saved payout account and
    records it as ``Paid``.
    """

    class Status(models.TextChoices):
        SCHEDULED = "Scheduled", "Scheduled"
        ELIGIBLE = "Eligible", "Eligible"
        PAID = "Paid", "Paid"
        CANCELLED = "Cancelled", "Cancelled"

    reference = models.CharField(max_length=24, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payouts"
    )
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name="payout"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True
    )
    available_at = models.DateTimeField(db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payouts",
    )
    note = models.CharField(max_length=255, blank=True)
    # Snapshot of where the money was sent (kept for the audit trail).
    payout_method = models.CharField(max_length=16, blank=True)
    payout_account_name = models.CharField(max_length=120, blank=True)
    payout_account_number = models.CharField(max_length=64, blank=True)
    payout_bank_name = models.CharField(max_length=120, blank=True)
    payout_phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status", "-created_at"]),
            models.Index(fields=["status", "available_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} · {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import uuid

            self.reference = f"PY-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @builtins.property
    def amount_display(self) -> str:
        return f"${float(self.amount or 0):,.0f}"

    @builtins.property
    def is_paid(self) -> bool:
        return self.status == self.Status.PAID

    @builtins.property
    def is_cancelled(self) -> bool:
        return self.status == self.Status.CANCELLED

    @builtins.property
    def can_pay(self) -> bool:
        return (
            self.status in (self.Status.SCHEDULED, self.Status.ELIGIBLE)
            and self.available_at <= timezone.now()
            and self.payment.is_successful
            and not self.payment.is_refunded
        )

    @builtins.property
    def payment_reference(self) -> str:
        return self.payment.reference if self.payment_id else "—"

    @builtins.property
    def booking_id(self) -> int | None:
        return self.payment.booking_id if self.payment_id else None

    @builtins.property
    def property_title(self) -> str:
        if not self.payment_id:
            return "—"
        if self.payment.booking_id:
            return self.payment.booking.property_title
        if self.payment.property_id:
            return self.payment.property.title
        return "—"


class Refund(models.Model):
    class Reason(models.TextChoices):
        CANCELLED_BY_RENTER = "cancelled_by_renter", "Cancelled by renter"
        CANCELLED_BY_OWNER = "cancelled_by_owner", "Cancelled by owner"
        REJECTED_BY_OWNER = "rejected_by_owner", "Rejected by owner"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PROCESSED = "Processed", "Processed"
        REJECTED = "Rejected", "Rejected"

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
    request_note = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests",
    )
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
