from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone
from django_bolt.exceptions import HTTPException

from accounts.console_api import (
    audit_logs_export,
    audit_logs_list,
    notification_message_reset,
    property_restore,
    refund_create,
    session_logout,
    sessions_export,
    sessions_list,
)
from accounts.models import AuditLog, LoginSession, PlatformSettings, Role, User
from bookings.models import Booking
from notifications.default_messages import DEFAULT_NOTIFICATION_MESSAGES
from listings.models import Property
from payments.models import Payment, Refund
from accounts.session_tracking import (
    end_login_session,
    extract_client_ip,
    is_public_ip,
    parse_user_agent,
    record_login_session,
)


class MockRequest:
    def __init__(self, query=None, session=None, headers=None):
        self.query = query or {}
        self.session = session if session is not None else SessionStore()
        self.headers = headers or {}
        self.params = {}
        self.body = b""
        self.user = None
        self.META = {}


class SessionTrackingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="security@example.com",
            username="securityuser",
            password="secret123",
            role=Role.RENTER,
        )

    def test_extract_client_ip_prefers_real_ip_and_rejects_junk(self):
        self.assertEqual(
            extract_client_ip(
                {
                    "X-Forwarded-For": "203.0.113.9, 10.0.0.1",
                    "X-Real-IP": "8.8.8.8",
                }
            ),
            "8.8.8.8",
        )
        self.assertEqual(
            extract_client_ip({"X-Forwarded-For": "198.51.100.4, 10.0.0.1"}),
            "198.51.100.4",
        )
        self.assertIsNone(extract_client_ip({"X-Real-IP": "not-an-ip"}))
        self.assertFalse(is_public_ip("127.0.0.1"))
        self.assertFalse(is_public_ip("10.0.0.2"))
        self.assertTrue(is_public_ip("8.8.8.8"))

    def test_parse_user_agent_summarises_device_and_browser(self):
        iphone = parse_user_agent(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
        )
        self.assertEqual(iphone["device_type"], LoginSession.DeviceType.MOBILE)
        self.assertEqual(iphone["browser"], "Safari")
        self.assertEqual(iphone["operating_system"], "iOS")

        windows = parse_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        )
        self.assertEqual(windows["device_type"], LoginSession.DeviceType.DESKTOP)
        self.assertEqual(windows["browser"], "Chrome")
        self.assertEqual(windows["operating_system"], "Windows")

        bot = parse_user_agent("Googlebot/2.1 (+http://www.google.com/bot.html)")
        self.assertEqual(bot["device_type"], LoginSession.DeviceType.BOT)

    def test_record_and_end_login_session(self):
        session = SessionStore()
        session.save()
        request = MockRequest(
            session=session,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/125.0",
                "X-Real-IP": "8.8.8.8",
            },
        )

        with patch(
            "accounts.session_tracking.lookup_ip_location",
            return_value={
                "country_code": "KH",
                "country": "Cambodia",
                "region": "Phnom Penh",
                "city": "Phnom Penh",
            },
        ):
            row = record_login_session(self.user, request, "Email")

        self.assertIsNotNone(row)
        self.assertEqual(row.session_key, session.session_key)
        self.assertEqual(row.user_id, self.user.pk)
        self.assertEqual(row.auth_method, "email")
        self.assertEqual(row.ip_address, "8.8.8.8")
        self.assertEqual(row.device_type, LoginSession.DeviceType.DESKTOP)
        self.assertEqual(row.browser, "Firefox")
        self.assertEqual(row.location_label, "Phnom Penh, Cambodia")
        self.assertIsNotNone(row.session_expires_at)

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.user, action=AuditLog.Action.LOGIN, entity="session"
            ).exists()
        )

        end_login_session(request)
        row.refresh_from_db()
        self.assertIsNotNone(row.logged_out_at)


class SecurityConsoleEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="viewer@example.com",
            username="viewer",
            password="secret123",
            role=Role.SUPERADMIN,
        )
        self.active_store = SessionStore()
        self.active_store.save()
        self.inactive_store = SessionStore()
        self.inactive_store.save()

        Session.objects.filter(session_key=self.inactive_store.session_key).update(
            expire_date=timezone.now() - timedelta(minutes=1)
        )

        self.active_session = LoginSession.objects.create(
            user=self.user,
            session_key=self.active_store.session_key,
            auth_method="email",
            ip_address="8.8.8.8",
            device_type=LoginSession.DeviceType.DESKTOP,
            browser="Chrome",
            operating_system="Linux",
            country_code="KH",
            country="Cambodia",
            city="Phnom Penh",
            session_expires_at=timezone.now() + timedelta(days=14),
        )
        self.inactive_session = LoginSession.objects.create(
            user=self.user,
            session_key=self.inactive_store.session_key,
            auth_method="google",
            ip_address="1.1.1.1",
            device_type=LoginSession.DeviceType.MOBILE,
            browser="Safari",
            operating_system="iOS",
            country="Thailand",
            city="Bangkok",
            logged_out_at=timezone.now(),
        )

    async def test_sessions_list_marks_current_and_counts_status(self):
        request = MockRequest(
            query={"page": "1", "page_size": "25"},
            session=self.active_store,
        )
        with patch(
            "accounts.console_api.login_required", new=AsyncMock(return_value=self.user)
        ):
            result = await sessions_list(request)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["inactive_count"], 1)
        current = next(item for item in result["sessions"] if item["is_current"])
        self.assertEqual(current["id"], self.active_session.pk)
        self.assertTrue(current["is_active"])
        self.assertEqual(current["location"], "Phnom Penh, Cambodia")
        self.assertEqual(
            {item["value"] for item in result["methods"]}, {"email", "google"}
        )

    async def test_sessions_list_prunes_old_logged_out_history(self):
        cutoff = timezone.now() - timedelta(
            days=settings.LOGIN_SESSION_HISTORY_DAYS + 1
        )
        old = await LoginSession.objects.acreate(
            user=self.user,
            session_key="old-signed-out-session",
            auth_method="email",
            logged_out_at=cutoff,
        )
        expired = await LoginSession.objects.acreate(
            user=self.user,
            session_key="old-expired-session",
            auth_method="email",
            session_expires_at=cutoff,
        )
        request = MockRequest(
            query={"page": "1", "page_size": "25"}, session=self.active_store
        )
        with patch(
            "accounts.console_api.login_required", new=AsyncMock(return_value=self.user)
        ):
            result = await sessions_list(request)

        self.assertEqual(result["total"], 2)
        self.assertFalse(await LoginSession.objects.filter(pk=old.pk).aexists())
        self.assertFalse(await LoginSession.objects.filter(pk=expired.pk).aexists())

    async def test_sessions_export_returns_utf8_csv(self):
        request = MockRequest(query={"status": "active"}, session=self.active_store)
        with patch(
            "accounts.console_api.login_required", new=AsyncMock(return_value=self.user)
        ):
            response = await sessions_export(request)

        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        self.assertIn("Signed in,User,Email", body)
        self.assertIn("viewer@example.com", body)
        self.assertIn("Chrome", body)
        self.assertNotIn("Safari", body)
        self.assertIn("attachment; filename=", response.headers["Content-Disposition"])

    async def test_sessions_are_scoped_to_the_signed_in_user(self):
        other = await User.objects.acreate(
            email="other@example.com", username="other", role=Role.RENTER
        )
        other_session = await LoginSession.objects.acreate(
            user=other,
            session_key="other-user-session",
            auth_method="email",
        )

        request = MockRequest(
            query={"page": "1", "page_size": "25"}, session=self.active_store
        )
        with patch(
            "accounts.console_api.login_required", new=AsyncMock(return_value=self.user)
        ):
            result = await sessions_list(request)
        self.assertEqual(result["total"], 2)
        self.assertTrue(
            all(item["user"]["id"] == self.user.pk for item in result["sessions"])
        )

        logout_request = MockRequest(session=self.active_store)
        logout_request.params = {"pk": str(other_session.pk)}
        with patch(
            "accounts.console_api.login_required", new=AsyncMock(return_value=self.user)
        ):
            with self.assertRaises(HTTPException):
                await session_logout(logout_request)

    async def test_audit_report_filters_and_builds_chart(self):
        await AuditLog.objects.acreate(
            actor=self.user,
            action=AuditLog.Action.LOGIN,
            entity="session",
            entity_id=str(self.user.pk),
            summary="login via email",
        )
        await AuditLog.objects.acreate(
            actor=self.user,
            action=AuditLog.Action.UPDATE,
            entity="user",
            entity_id=str(self.user.pk),
            summary="updated user",
        )
        request = MockRequest(query={"action": "login"})
        with patch(
            "accounts.console_api.superadmin_required", new=AsyncMock(return_value=self.user)
        ):
            result = await audit_logs_list(request)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["logs"][0]["action"], "login")
        self.assertEqual(result["by_action"], [{"action": "login", "n": 1}])
        self.assertEqual(len(result["by_day"]), 14)
        self.assertEqual(sum(day["count"] for day in result["by_day"]), 1)
        self.assertIn({"value": "user", "label": "User"}, result["entities"])

    async def test_audit_export_returns_rows(self):
        await AuditLog.objects.acreate(
            actor=self.user,
            action=AuditLog.Action.STATUS,
            entity="booking",
            entity_id="42",
            summary="status changed",
        )
        request = MockRequest(query={"entity": "booking"})
        with patch(
            "accounts.console_api.superadmin_required", new=AsyncMock(return_value=self.user)
        ):
            response = await audit_logs_export(request)

        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        self.assertIn("Time,Actor,Actor email,Action", body)
        self.assertIn("status changed", body)
        self.assertIn("booking", body)


class ConsolePropertyRestoreTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-restore@example.com",
            username="adminrestore",
            password="secret123",
            role=Role.SUPERADMIN,
        )
        self.owner = User.objects.create_user(
            email="owner-restore@example.com",
            username="ownerrestore",
            password="secret123",
            role=Role.OWNER,
        )
        self.property = Property.objects.create(
            owner=self.owner,
            title="Restorable villa",
            location="Siem Reap",
            price_per_month=500,
            is_active=False,
        )

    async def test_restore_returns_removed_property_to_browsing(self):
        request = MockRequest()
        request.user = self.admin
        request.params = {"pk": str(self.property.pk)}

        response = await property_restore(request)

        self.assertEqual(response, {"ok": True, "restored": self.property.pk, "is_active": True})
        await self.property.arefresh_from_db()
        self.assertTrue(self.property.is_active)
        self.assertTrue(
            await AuditLog.objects.filter(
                actor=self.admin,
                action=AuditLog.Action.STATUS,
                entity="property",
                entity_id=str(self.property.pk),
                summary__contains="restored",
            ).aexists()
        )

    async def test_restore_is_idempotent_for_active_property(self):
        self.property.is_active = True
        await self.property.asave(update_fields=["is_active"])
        request = MockRequest()
        request.user = self.admin
        request.params = {"pk": str(self.property.pk)}

        response = await property_restore(request)

        self.assertEqual(response, {"ok": True, "restored": self.property.pk, "is_active": True})
        self.assertEqual(
            await AuditLog.objects.filter(entity="property", entity_id=str(self.property.pk)).acount(),
            0,
        )


class ConsoleNotificationMessageResetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-notifications@example.com",
            username="adminnotifications",
            password="secret123",
            role=Role.SUPERADMIN,
        )

    async def test_reset_restores_only_the_requested_message(self):
        configured = deepcopy(DEFAULT_NOTIFICATION_MESSAGES)
        configured[0]["body_en"] = "Broken message without parameters"
        configured[1]["title_en"] = "Custom second title"
        platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)
        platform.notification_messages = configured
        await platform.asave(update_fields=["notification_messages"])

        request = MockRequest()
        request.user = self.admin
        request.body = b'{"key": "notif_new_request"}'

        response = await notification_message_reset(request)

        messages = response["settings"]["notification_messages"]
        self.assertEqual(messages[0], DEFAULT_NOTIFICATION_MESSAGES[0])
        self.assertEqual(messages[1]["title_en"], "Custom second title")
        await platform.arefresh_from_db()
        self.assertEqual(platform.notification_messages[0], DEFAULT_NOTIFICATION_MESSAGES[0])
        self.assertEqual(platform.notification_messages[1]["title_en"], "Custom second title")
        self.assertTrue(
            await AuditLog.objects.filter(
                actor=self.admin,
                action=AuditLog.Action.UPDATE,
                entity="settings",
                summary__contains="notif_new_request",
            ).aexists()
        )

    async def test_reset_rejects_unknown_key(self):
        request = MockRequest()
        request.user = self.admin
        request.body = b'{"key": "not_a_real_key"}'

        with self.assertRaises(Exception) as context:
            await notification_message_reset(request)

        self.assertEqual(getattr(context.exception, "status_code", None), 422)


class ConsoleRefundCreateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="staff-admin@example.com",
            username="staffadmin",
            password="secret123",
            role=Role.RENTER,
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            email="refund-owner@example.com",
            username="refundowner",
            password="secret123",
            role=Role.OWNER,
        )
        self.renter = User.objects.create_user(
            email="refund-renter@example.com",
            username="refundrenter",
            password="secret123",
            role=Role.RENTER,
        )
        self.property = Property.objects.create(
            owner=self.owner,
            title="Refundable villa",
            location="Phnom Penh",
            price_per_month=400,
        )
        self.booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            monthly_rent=400,
        )
        self.payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=400,
        )

    async def test_staff_admin_can_issue_refund(self):
        request = MockRequest()
        request.user = self.admin
        request.body = f'{{"payment": {self.payment.pk}, "reason": "other"}}'.encode()

        with (
            patch("accounts.console_api.notify_refund_team", return_value=None),
            patch("accounts.console_api.cancel_payout_for_payment", return_value=None),
        ):
            response = await refund_create(request)

        self.assertEqual(response["refund"]["status"], Refund.Status.PENDING)
        await self.payment.arefresh_from_db()
        self.assertEqual(self.payment.refund_status, Payment.RefundStatus.PENDING)
        self.assertTrue(
            await Refund.objects.filter(payment=self.payment, requested_by=self.admin).aexists()
        )
