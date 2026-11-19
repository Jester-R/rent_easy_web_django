from __future__ import annotations

from builtins import property as prop

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """A direct renter/owner chat or a one-to-one refund support chat."""

    class RefundParty(models.TextChoices):
        RENTER = "renter", "Renter"
        OWNER = "owner", "Owner"

    property = models.ForeignKey(
        "listings.Property", on_delete=models.CASCADE, related_name="conversations"
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_renter",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_owner",
    )
    refund = models.ForeignKey(
        "payments.Refund",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    refund_party = models.CharField(
        max_length=10,
        choices=RefundParty.choices,
        blank=True,
    )
    refund_participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="refund_support_conversations",
    )
    support_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_support_admin_conversations",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "renter", "owner"],
                condition=models.Q(refund__isnull=True),
                name="unique_direct_conversation_participants",
            ),
            models.UniqueConstraint(
                fields=["refund", "refund_party"],
                condition=models.Q(refund__isnull=False),
                name="unique_refund_support_chat_per_party",
            ),
        ]
        indexes = [
            models.Index(fields=["renter", "-updated_at"]),
            models.Index(fields=["owner", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"conversation:{self.pk}"

    def other_party(self, user):
        if self.refund_id:
            if user.pk == self.refund_participant_id:
                return self.support_admin
            if user.pk == self.support_admin_id:
                return self.refund_participant
            return self.support_admin
        return self.owner if self.renter_id == user.pk else self.renter

    @prop
    def refund_label(self) -> str:
        if not self.refund_id:
            return ""
        participant = (
            self.refund_participant.display_name
            if self.refund_participant_id
            else (self.get_refund_party_display() if self.refund_party else "Support")
        )
        return f"Refund chat · {participant}"

    @prop
    def property_title(self) -> str:
        return self.property.title if self.property_id else ""

    @prop
    def property_cover(self) -> str:
        return self.property.cover_image if self.property_id else ""

    @prop
    def property_is_active(self) -> bool:
        return bool(self.property_id and self.property.is_active)

    @prop
    def is_refund_support(self) -> bool:
        return self.refund_id is not None

    @prop
    def refund_status(self) -> str:
        return self.refund.status if self.refund_id else ""

    @prop
    def refund_payment_id(self) -> int | None:
        return self.refund.payment_id if self.refund_id else None

    @prop
    def refund_reference(self) -> str:
        return self.refund.reference if self.refund_id else ""

    def get_absolute_url(self) -> str:
        return f"/messages/{self.pk}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages"
    )
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self) -> str:
        return f"message:{self.pk}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
