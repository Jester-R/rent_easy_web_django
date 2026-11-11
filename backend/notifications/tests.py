from unittest.mock import patch

from django.test import TestCase

from accounts.models import Role, User
from notifications.models import Notification
from notifications.services import notify


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
