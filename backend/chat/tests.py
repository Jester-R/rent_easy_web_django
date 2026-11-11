from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from chat.api import _notify_new_message
from chat.models import Conversation
from listings.models import Property
from notifications.models import Notification


class ChatNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="chat-owner@example.test",
            username="chat-owner",
            password="x",
            role=Role.OWNER,
        )
        cls.renter = User.objects.create_user(
            email="chat-renter@example.test",
            username="chat-renter",
            password="x",
            role=Role.RENTER,
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Chat Test Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("100.00"),
            bedrooms=1,
            bathrooms=1,
            description="Test",
            category="apartment",
        )
        cls.conversation = Conversation.objects.create(
            property=cls.property, renter=cls.renter, owner=cls.owner
        )

    async def test_new_message_notifies_the_other_party(self):
        conversation = await Conversation.objects.select_related(
            "property", "renter", "owner"
        ).aget(pk=self.conversation.pk)

        await _notify_new_message(conversation, self.renter)

        notification = await Notification.objects.filter(
            recipient=self.owner, kind=Notification.Kind.CHAT_MESSAGE
        ).afirst()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title_key, "notif_chat_message")
        self.assertEqual(notification.link, f"/messages/{conversation.pk}")
        self.assertEqual(notification.params["sender"], self.renter.display_name)
        self.assertEqual(notification.params["title"], self.property.title)
        self.assertEqual(
            await Notification.objects.filter(recipient=self.renter).acount(), 0
        )
