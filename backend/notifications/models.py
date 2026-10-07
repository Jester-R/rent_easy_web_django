from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """In-app notification feed (the web counterpart of NotificationBell)."""

    class Kind(models.TextChoices):
        BOOKING_REQUEST = "booking_request", "Booking request"
        BOOKING_UPDATE = "booking_update", "Booking update"
        BOOKING_APPROVED = "booking_approved", "Booking approved"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        REFUND_PROCESSED = "refund_processed", "Refund processed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    title_key = models.CharField(max_length=64)
    body_key = models.CharField(max_length=64)
    params = models.JSONField(default=dict, blank=True)
    link = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=24, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.title_key}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def get_absolute_url(self) -> str:
        return self.link or "/notifications/"


class NotificationSeen(models.Model):
    """Tracks the last time a user opened the bell, so the badge can be derived."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_seen",
    )
    seen_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"seen:{self.user_id}"
