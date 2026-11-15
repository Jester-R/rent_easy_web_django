from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone

from accounts.console_api import (
    audit_logs_export,
    audit_logs_list,
    sessions_export,
    sessions_list,
)
from accounts.models import AuditLog, LoginSession, Role, User
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
            "accounts.console_api.superadmin_required", new=AsyncMock(return_value=self.user)
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

    async def test_sessions_export_returns_utf8_csv(self):
        request = MockRequest(query={"status": "active"}, session=self.active_store)
        with patch(
            "accounts.console_api.superadmin_required", new=AsyncMock(return_value=self.user)
        ):
            response = await sessions_export(request)

        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        self.assertIn("Signed in,User,Email", body)
        self.assertIn("viewer@example.com", body)
        self.assertIn("Chrome", body)
        self.assertNotIn("Safari", body)
        self.assertIn("attachment; filename=", response.headers["Content-Disposition"])

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
