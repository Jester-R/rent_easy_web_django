from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.models import Role, User
from listings.models import Property
from notifications.models import Notification
from notifications.rendering import notification_copy, render
from notifications.services import notify
from notifications.telegram import _message_text
from payments.services import create_booking


class NotificationChannelTests(TestCase):
    def _user(self, email="renter@real-domain.com", verified=True, **extra):
        return User.objects.create_user(
            email=email,
            username=extra.pop("username", "renter_notify"),
            password="secret123",
            role=Role.RENTER,
            is_email_verified=verified,
            **extra,
        )

    def test_notify_dispatches_telegram_and_email(self):
        user = self._user()
        with patch(
            "notifications.telegram.send_telegram_notification"
        ) as telegram_send, patch(
            "notifications.email.send_email_notification"
        ) as email_send, self.captureOnCommitCallbacks(execute=True):
            notification = notify(
                user,
                Notification.Kind.ACCOUNT_SIGN_IN,
                "notif_account_signed_in",
                "notif_account_signed_in_body",
                params={"provider": "email", "time": "now"},
            )

        telegram_send.assert_called_once_with(notification.pk)
        email_send.assert_called_once_with(notification.pk)

    def test_booking_request_includes_full_details(self):
        owner = User.objects.create_user(
            email="booking-owner@real-domain.com",
            username="booking-owner",
            password="secret123",
            role=Role.OWNER,
        )
        renter = User.objects.create_user(
            email="booking-renter@real-domain.com",
            username="booking-renter",
            password="secret123",
            role=Role.RENTER,
        )
        property_obj = Property.objects.create(
            owner=owner,
            title="BKK1 Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("450.00"),
            bedrooms=2,
            bathrooms=1,
            description="Test",
            category="apartment",
        )

        booking = create_booking(
            property_obj=property_obj,
            renter=renter,
            move_in_date=date(2026, 12, 1),
            lease_months=6,
            note="I would like to move in with my cat.",
        )

        notification = Notification.objects.get(
            recipient=owner, kind=Notification.Kind.BOOKING_REQUEST
        )
        self.assertEqual(notification.params["reference"], booking.reference)
        self.assertEqual(notification.params["amount"], "$450")
        self.assertEqual(notification.params["move_in"], "01 Dec 2026")
        self.assertEqual(notification.params["lease"], "6 months")
        self.assertEqual(
            notification.params["note"], "I would like to move in with my cat."
        )
        copy = notification_copy(notification)
        body = render(copy["body_en"], copy["params"])
        self.assertIn("BKK1 Apartment", body)
        self.assertIn("01 Dec 2026", body)
        self.assertIn("I would like to move in with my cat.", body)

    def test_booking_request_accepts_iso_date_strings(self):
        owner = User.objects.create_user(
            email="booking-owner-iso@real-domain.com",
            username="booking-owner-iso",
            password="secret123",
            role=Role.OWNER,
        )
        renter = User.objects.create_user(
            email="booking-renter-iso@real-domain.com",
            username="booking-renter-iso",
            password="secret123",
            role=Role.RENTER,
        )
        property_obj = Property.objects.create(
            owner=owner,
            title="ISO Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("450.00"),
            bedrooms=2,
            bathrooms=1,
            description="Test",
            category="apartment",
        )

        booking = create_booking(
            property_obj=property_obj,
            renter=renter,
            move_in_date="2026-12-01",
            end_date="2027-06-01",
            lease_months=6,
        )

        self.assertEqual(booking.move_in_date, date(2026, 12, 1))
        self.assertEqual(booking.end_date, date(2027, 6, 1))
        notification = Notification.objects.get(
            recipient=owner, kind=Notification.Kind.BOOKING_REQUEST
        )
        self.assertEqual(notification.params["move_in"], "01 Dec 2026")
        self.assertEqual(notification.params["lease"], "6 months (until 01 Jun 2027)")

    @override_settings(FRONTEND_BASE_URL="https://renteasy.example")
    def test_telegram_message_links_to_the_notification_page(self):
        user = self._user()
        notification = Notification.objects.create(
            recipient=user,
            kind=Notification.Kind.CHAT_MESSAGE,
            title_key="notif_chat_message",
            body_key="notif_chat_message_body",
            params={
                "sender": "Demo Owner",
                "message": "Is the apartment still available?",
                "title": "BKK1 Apartment",
            },
            link="/messages/42",
        )

        text = _message_text(notification)

        self.assertIn("Is the apartment still available?", text)
        self.assertIn("https://renteasy.example/messages/42", text)
        self.assertTrue(text.endswith("https://renteasy.example/messages/42"))

    def test_email_channel_sends_to_verified_address(self):
        from notifications.email import send_email_notification

        user = self._user(email="mailer@real-domain.com")
        notification = Notification.objects.create(
            recipient=user,
            kind=Notification.Kind.ANNOUNCEMENT,
            title_key="admin_broadcast",
            body_key="admin_broadcast_body",
            params={
                "message_overrides": {
                    "title_en": "Hello",
                    "body_en": "Your notification body",
                }
            },
        )
        with patch("notifications.email.send_mail") as send:
            sent = send_email_notification(notification.pk)

        self.assertTrue(sent)
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["recipient_list"], [user.email])

    def test_email_channel_skips_telegram_only_account(self):
        from notifications.email import send_email_notification

        user = self._user(
            email="telegram_12345@telegram.local",
            verified=False,
            username="telegram_only",
        )
        notification = Notification.objects.create(
            recipient=user,
            kind=Notification.Kind.ACCOUNT_CREATED,
            title_key="notif_account_created",
            body_key="notif_account_created_body",
        )
        with patch("notifications.email.send_mail") as send:
            sent = send_email_notification(notification.pk)

        self.assertFalse(sent)
        send.assert_not_called()
