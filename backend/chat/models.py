from __future__ import annotations

from builtins import property as prop

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """A renter <-> owner message thread, usually scoped to a property."""

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
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "renter", "owner"],
                name="unique_conversation_participants",
            )
        ]
        indexes = [
            models.Index(fields=["renter", "-updated_at"]),
            models.Index(fields=["owner", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"conversation:{self.pk}"

    def other_party(self, user):
        return self.owner if self.renter_id == user.pk else self.renter

    @prop
    def property_title(self) -> str:
        return self.property.title if self.property_id else ""

    @prop
    def property_cover(self) -> str:
        return self.property.cover_image if self.property_id else ""


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
