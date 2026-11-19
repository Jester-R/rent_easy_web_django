from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.utils import timezone
from django_bolt.exceptions import HTTPException

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
from chat.api import (
    _notify_new_message,
    _summary,
    booking_chat,
    conversations,
    send_message,
)
from chat.models import Conversation
from listings.models import Property
from notifications.default_messages import DEFAULT_NOTIFICATION_MESSAGES
from notifications.models import Notification
from notifications.rendering import render
from payments.models import Payment, Refund
from payments.services import (
    RefundRequestError,
    accept_refund,
    ensure_refund_chat,
    request_booking_cancellation,
)


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

        message = "Is the apartment still available?"
        await _notify_new_message(conversation, self.renter, message)

        notification = await Notification.objects.filter(
            recipient=self.owner, kind=Notification.Kind.CHAT_MESSAGE
        ).afirst()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title_key, "notif_chat_message")
        self.assertEqual(notification.link, f"/messages/{conversation.pk}")
        self.assertEqual(notification.params["sender"], self.renter.display_name)
        self.assertEqual(notification.params["title"], self.property.title)
        self.assertEqual(notification.params["message"], message)
        template = next(
            item
            for item in DEFAULT_NOTIFICATION_MESSAGES
            if item["key"] == "notif_chat_message"
        )
        self.assertIn(message, render(template["body_en"], notification.params))
        self.assertEqual(
            await Notification.objects.filter(recipient=self.renter).acount(), 0
        )


class RefundChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="refund-chat-owner@example.test",
            username="refund-chat-owner",
            password="x",
            role=Role.OWNER,
        )
        cls.renter = User.objects.create_user(
            email="refund-chat-renter@example.test",
            username="refund-chat-renter",
            password="x",
            role=Role.RENTER,
        )
        cls.admin = User.objects.create_user(
            email="refund-chat-admin@example.test",
            username="refund-chat-admin",
            password="x",
            role=Role.SUPERADMIN,
            is_staff=True,
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Refund Chat Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("250.00"),
            bedrooms=1,
            bathrooms=1,
            description="Test",
            category="apartment",
        )
        cls.booking = Booking.objects.create(
            property=cls.property,
            renter=cls.renter,
            owner=cls.owner,
            status=BookingStatus.CONFIRMED,
            monthly_rent=Decimal("250.00"),
        )

    def _request_refund(self) -> Refund:
        payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("250.00"),
            method=Payment.Method.ABA_MOCK,
            status=Payment.Status.SUCCESS,
            provider=Payment.Provider.MOCK,
            paid_at=timezone.now(),
            gateway_payload={},
        )
        self.booking.payment = payment
        self.booking.save(update_fields=["payment"])
        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Need to discuss the refund"
        )
        self.assertEqual(code, "")
        return refund

    def _load(self, conversation: Conversation) -> Conversation:
        return Conversation.objects.select_related(
            "property",
            "renter",
            "owner",
            "refund",
            "refund_participant",
            "support_admin",
        ).get(pk=conversation.pk)

    def _request(self, user, body: str = ""):
        return SimpleNamespace(
            params={"pk": str(self.conversation.pk)},
            query={"page": "1", "page_size": "20"},
            body=json.dumps({"body": body}).encode() if body else b"",
            user=user,
        )

    def test_refund_request_does_not_create_chat_thread(self):
        refund = self._request_refund()
        self.assertFalse(Conversation.objects.filter(refund=refund).exists())

    def test_refund_chats_are_one_to_one_and_created_after_acceptance(self):
        refund = self._request_refund()
        with self.assertRaises(RefundRequestError) as blocked:
            ensure_refund_chat(refund, party="renter", admin=self.admin)
        self.assertEqual(blocked.exception.code, "refund_not_accepted")

        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        renter_chat = self._load(ensure_refund_chat(refund, party="renter", admin=self.admin))
        owner_chat = self._load(ensure_refund_chat(refund, party="owner", admin=self.admin))

        self.assertEqual(renter_chat.refund_party, "renter")
        self.assertEqual(renter_chat.refund_participant_id, self.renter.pk)
        self.assertEqual(renter_chat.support_admin_id, self.admin.pk)
        self.assertEqual(renter_chat.other_party(self.renter).pk, self.admin.pk)
        self.assertEqual(renter_chat.get_absolute_url(), f"/messages/{renter_chat.pk}")
        self.assertEqual(owner_chat.refund_party, "owner")
        self.assertEqual(owner_chat.refund_participant_id, self.owner.pk)
        self.assertEqual(owner_chat.other_party(self.owner).pk, self.admin.pk)
        self.assertNotEqual(renter_chat.pk, owner_chat.pk)

        summary = async_to_sync(_summary)(renter_chat, self.admin)
        self.assertTrue(summary["is_refund_support"])
        self.assertEqual(summary["refund_id"], refund.pk)
        self.assertEqual(summary["refund_status"], Refund.Status.ACCEPTED)
        self.assertIn(self.renter.display_name, summary["refund_label"])

    def test_booking_chat_opens_general_chat_for_inactive_property(self):
        self.property.is_active = False
        self.property.save(update_fields=["is_active"])
        request = SimpleNamespace(
            params={"pk": str(self.booking.pk)},
            query={},
            body=b"",
            user=self.renter,
        )

        renter_result = async_to_sync(booking_chat)(request)
        conversation_id = renter_result["conversation"]["id"]
        self.assertFalse(renter_result["conversation"]["is_refund_support"])

        request.user = self.owner
        owner_result = async_to_sync(booking_chat)(request)
        self.assertEqual(owner_result["conversation"]["id"], conversation_id)

    def test_admins_see_all_refund_chats_and_participants_see_only_their_own(self):
        refund = self._request_refund()
        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        renter_chat = ensure_refund_chat(refund, party="renter", admin=self.admin)
        owner_chat = ensure_refund_chat(refund, party="owner", admin=self.admin)

        self.conversation = renter_chat
        request = self._request(self.admin)
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            result = async_to_sync(conversations)(request)
        ids = {c["id"] for c in result["conversations"]}
        self.assertIn(renter_chat.pk, ids)
        self.assertIn(owner_chat.pk, ids)

        request = self._request(self.renter)
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.renter)):
            result = async_to_sync(conversations)(request)
        ids = {c["id"] for c in result["conversations"]}
        self.assertIn(renter_chat.pk, ids)
        self.assertNotIn(owner_chat.pk, ids)

        self.conversation = owner_chat
        request = self._request(self.owner)
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.owner)):
            result = async_to_sync(conversations)(request)
        ids = {c["id"] for c in result["conversations"]}
        self.assertIn(owner_chat.pk, ids)
        self.assertNotIn(renter_chat.pk, ids)

    def test_conversations_can_be_filtered_by_refund_or_general(self):
        refund = self._request_refund()
        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        refund_chat = ensure_refund_chat(refund, party="renter", admin=self.admin)
        self.conversation = refund_chat
        general_chat = Conversation.objects.create(
            property=self.property, renter=self.renter, owner=self.owner
        )

        request = self._request(self.admin)
        request.query["chat_type"] = "refund"
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            result = async_to_sync(conversations)(request)
        ids = {c["id"] for c in result["conversations"]}
        self.assertIn(refund_chat.pk, ids)
        self.assertNotIn(general_chat.pk, ids)

        request = self._request(self.renter)
        request.query["chat_type"] = "general"
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.renter)):
            result = async_to_sync(conversations)(request)
        ids = {c["id"] for c in result["conversations"]}
        self.assertIn(general_chat.pk, ids)
        self.assertNotIn(refund_chat.pk, ids)

    def test_conversations_can_be_filtered_by_participant_property_date_and_search(self):
        refund = self._request_refund()
        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        renter_chat = ensure_refund_chat(refund, party="renter", admin=self.admin)
        owner_chat = ensure_refund_chat(refund, party="owner", admin=self.admin)
        self.conversation = renter_chat
        today = timezone.now().date().isoformat()

        request = self._request(self.admin)
        request.query.update({
            "chat_type": "refund",
            "participant": "owner",
            "property": self.property.title,
            "date_from": today,
            "date_to": today,
            "search": self.owner.display_name,
        })
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            result = async_to_sync(conversations)(request)
        self.assertEqual({c["id"] for c in result["conversations"]}, {owner_chat.pk})

        request.query["property"] = "No such property"
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            result = async_to_sync(conversations)(request)
        self.assertEqual(result["total"], 0)

    def test_admin_cannot_reply_before_acceptance(self):
        refund = self._request_refund()
        self.conversation = Conversation.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            refund=refund,
            refund_party="renter",
            refund_participant=self.renter,
            support_admin=self.admin,
        )

        request = self._request(self.admin, "Please wait for review")
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            with self.assertRaises(HTTPException) as error:
                async_to_sync(send_message)(request)
        self.assertEqual(error.exception.detail, "refund_not_accepted")

        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        request = self._request(self.admin, "Refund accepted")
        with patch("chat.api.login_required", new=AsyncMock(return_value=self.admin)):
            result = async_to_sync(send_message)(request)
        self.assertEqual(result["message"]["body"], "Refund accepted")

    def test_refund_chat_notifications_go_only_to_the_participant(self):
        refund = self._request_refund()
        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        renter_chat = self._load(ensure_refund_chat(refund, party="renter", admin=self.admin))
        owner_chat = self._load(ensure_refund_chat(refund, party="owner", admin=self.admin))
        Notification.objects.all().delete()

        async_to_sync(_notify_new_message)(renter_chat, self.renter, "Hello")
        admin_notification = Notification.objects.filter(recipient=self.admin).first()
        self.assertIsNotNone(admin_notification)
        self.assertEqual(admin_notification.title_key, "notif_refund_message")
        self.assertEqual(admin_notification.link, f"/messages/{renter_chat.pk}")
        self.assertFalse(Notification.objects.filter(recipient=self.owner).exists())
        template = next(
            item
            for item in DEFAULT_NOTIFICATION_MESSAGES
            if item["key"] == "notif_refund_message"
        )
        self.assertIn(
            refund.reference, render(template["body_en"], admin_notification.params)
        )

        Notification.objects.all().delete()
        async_to_sync(_notify_new_message)(renter_chat, self.admin, "Accepted")
        self.assertTrue(Notification.objects.filter(recipient=self.renter).exists())
        self.assertFalse(
            Notification.objects.filter(recipient=self.owner).exists()
        )
        self.assertEqual(Conversation.objects.filter(pk=owner_chat.pk).count(), 1)
