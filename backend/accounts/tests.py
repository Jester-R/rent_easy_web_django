from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from accounts.google_oauth import (
    generate_oauth_state,
    get_authorization_url,
    get_or_create_google_user,
    is_google_oauth_configured,
    verify_oauth_state,
)
from accounts.models import ApprovalStatus, EmailVerification, PlatformSettings, Role, User


class GoogleOAuthStateTests(TestCase):
    def test_state_generation_and_verification(self):
        state = generate_oauth_state(role=Role.OWNER, next_url="/owner", redirect_uri="http://localhost:4200/callback")
        self.assertIsInstance(state, str)

        data = verify_oauth_state(state)
        self.assertIsNotNone(data)
        self.assertEqual(data["role"], Role.OWNER)
        self.assertEqual(data["next"], "/owner")
        self.assertEqual(data["redirect_uri"], "http://localhost:4200/callback")

    def test_tampered_state_rejected(self):
        state = generate_oauth_state(role=Role.RENTER)
        tampered = state + "tamper"
        self.assertIsNone(verify_oauth_state(tampered))

    def test_empty_state_rejected(self):
        self.assertIsNone(verify_oauth_state(""))
        self.assertIsNone(verify_oauth_state(None))


class GoogleOAuthUserCreationTests(TestCase):
    async def test_create_new_renter_user(self):
        user_info = {
            "sub": "google-uid-12345",
            "email": "sarah.connor@example.com",
            "name": "Sarah Connor",
            "picture": "https://lh3.googleusercontent.com/avatar.jpg",
        }
        user, created, block = await get_or_create_google_user(user_info, requested_role=Role.RENTER)

        self.assertTrue(created)
        self.assertIsNone(block)
        self.assertEqual(user.email, "sarah.connor@example.com")
        self.assertEqual(user.full_name, "Sarah Connor")
        self.assertEqual(user.google_id, "google-uid-12345")
        self.assertEqual(user.avatar_url, "https://lh3.googleusercontent.com/avatar.jpg")
        self.assertEqual(user.role, Role.RENTER)
        self.assertTrue(user.is_active)
        self.assertEqual(user.approval_status, ApprovalStatus.APPROVED)
        self.assertFalse(user.has_usable_password())

    async def test_create_new_owner_user_pending_approval(self):
        platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)
        platform.auto_approve_owners = False
        await platform.asave()

        user_info = {
            "sub": "google-owner-999",
            "email": "owner.smith@example.com",
            "name": "Owner Smith",
            "picture": "",
        }
        user, created, block = await get_or_create_google_user(user_info, requested_role=Role.OWNER)

        self.assertTrue(created)
        self.assertEqual(block, "approval_pending")
        self.assertEqual(user.role, Role.OWNER)
        self.assertFalse(user.is_active)
        self.assertEqual(user.approval_status, ApprovalStatus.PENDING)

    async def test_link_existing_user_by_email(self):
        existing = await User.objects.acreate(
            email="existing@example.com",
            username="existinguser",
            full_name="Existing User",
            role=Role.RENTER,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        user_info = {
            "sub": "google-uid-777",
            "email": "existing@example.com",
            "name": "Existing User",
            "picture": "https://lh3.googleusercontent.com/avatar2.jpg",
        }
        user, created, block = await get_or_create_google_user(user_info, requested_role=Role.RENTER)

        self.assertFalse(created)
        self.assertIsNone(block)
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.google_id, "google-uid-777")
        self.assertEqual(user.avatar_url, "https://lh3.googleusercontent.com/avatar2.jpg")

    async def test_link_existing_user_replaces_placeholder_profile(self):
        existing = await User.objects.acreate(
            email="placeholder@example.com",
            username="tester",
            full_name="tester",
            avatar_url="",
            role=Role.RENTER,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        user_info = {
            "sub": "google-uid-placeholder",
            "email": "placeholder@example.com",
            "name": "Raky Ruu",
            "picture": "https://lh3.googleusercontent.com/new-avatar.jpg",
        }
        user, created, block = await get_or_create_google_user(
            user_info, requested_role=Role.RENTER
        )

        self.assertFalse(created)
        self.assertIsNone(block)
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.full_name, "Raky Ruu")
        self.assertEqual(
            user.avatar_url, "https://lh3.googleusercontent.com/new-avatar.jpg"
        )

    async def test_link_existing_user_preserves_custom_profile(self):
        existing = await User.objects.acreate(
            email="custom@example.com",
            username="customuser",
            full_name="My Custom Name",
            avatar_url="data:image/png;base64,abc123",
            role=Role.RENTER,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        user_info = {
            "sub": "google-uid-custom",
            "email": "custom@example.com",
            "name": "Google Name",
            "picture": "https://lh3.googleusercontent.com/google-avatar.jpg",
        }
        user, created, block = await get_or_create_google_user(
            user_info, requested_role=Role.RENTER
        )

        self.assertFalse(created)
        self.assertIsNone(block)
        self.assertEqual(user.full_name, "My Custom Name")
        self.assertEqual(user.avatar_url, "data:image/png;base64,abc123")

    async def test_existing_google_user_refreshes_google_avatar(self):
        existing = await User.objects.acreate(
            email="refresh@example.com",
            username="refreshuser",
            full_name="Refresh User",
            avatar_url="https://lh3.googleusercontent.com/old-avatar.jpg",
            google_id="google-uid-refresh",
            role=Role.RENTER,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        user_info = {
            "sub": "google-uid-refresh",
            "email": "refresh@example.com",
            "name": "Refresh User",
            "picture": "https://lh3.googleusercontent.com/new-avatar.jpg",
        }
        user, created, block = await get_or_create_google_user(
            user_info, requested_role=Role.RENTER
        )

        self.assertFalse(created)
        self.assertIsNone(block)
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.full_name, "Refresh User")
        self.assertEqual(
            user.avatar_url, "https://lh3.googleusercontent.com/new-avatar.jpg"
        )

    async def test_inactive_existing_user_blocked(self):
        await User.objects.acreate(
            email="disabled@example.com",
            username="disableduser",
            google_id="google-uid-disabled",
            is_active=False,
            approval_status=ApprovalStatus.APPROVED,
        )

        user_info = {
            "sub": "google-uid-disabled",
            "email": "disabled@example.com",
        }
        user, created, block = await get_or_create_google_user(user_info)
        self.assertFalse(created)
        self.assertEqual(block, "not_authorized")


class GoogleOAuthConfigurationTests(TestCase):
    @override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET="")
    def test_unconfigured(self):
        self.assertFalse(is_google_oauth_configured())

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
        GOOGLE_OAUTH_REDIRECT_URI="http://localhost:4200/api/auth/google/callback/",
    )
    def test_configured_url_generation(self):
        self.assertTrue(is_google_oauth_configured())
        url = get_authorization_url(role=Role.RENTER, next_url="/rent")
        self.assertIn("accounts.google.com", url)
        self.assertIn("client_id=mock-client-id", url)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A4200%2Fapi%2Fauth%2Fgoogle%2Fcallback%2F", url)
        self.assertIn("state=", url)


class MockBoltRequest:
    def __init__(self, query=None, body=b"", session=None):
        from django.contrib.sessions.backends.db import SessionStore

        self.query = query or {}
        self.body = body
        self.session = session if session is not None else SessionStore()
        self.user = None
        self.META = {}


class GoogleOAuthHandlerTests(TestCase):
    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
    )
    async def test_config_view(self):
        from accounts.api import google_oauth_config_view
        req = MockBoltRequest()
        res = await google_oauth_config_view(req)
        self.assertTrue(res["enabled"])
        self.assertEqual(res["client_id"], "mock-client-id")

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
    )
    async def test_url_view(self):
        from accounts.api import google_oauth_url_view
        req = MockBoltRequest(query={"role": "owner", "next": "/owner"})
        res = await google_oauth_url_view(req)
        self.assertTrue(res["enabled"])
        self.assertIn("accounts.google.com", res["url"])

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
        FRONTEND_BASE_URL="http://localhost:4200",
    )
    async def test_login_view_redirects_to_google(self):
        from accounts.api import google_oauth_login_view
        req = MockBoltRequest(query={"role": "renter"})
        res = await google_oauth_login_view(req)
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.url.startswith("https://accounts.google.com"))

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
        FRONTEND_BASE_URL="http://localhost:4200",
    )
    async def test_callback_post_success(self):
        import json
        from accounts.api import google_oauth_callback_post

        state = generate_oauth_state(role=Role.RENTER, next_url="/rent")
        req = MockBoltRequest(
            body=json.dumps({"code": "mock-code", "state": state}).encode("utf-8")
        )

        fake_user_info = {
            "sub": "google-user-9999",
            "email": "auto.test@example.com",
            "name": "Auto Tester",
            "picture": "",
        }

        with patch("accounts.api.exchange_code_for_user_info", return_value=fake_user_info):
            res = await google_oauth_callback_post(req)
            self.assertTrue(res["ok"])
            self.assertEqual(res["status"], "active")
            self.assertEqual(res["user"]["email"], "auto.test@example.com")
            self.assertEqual(res["redirect"], "/rent")

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="mock-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="mock-client-secret",
        FRONTEND_BASE_URL="http://localhost:4200",
    )
    async def test_callback_get_success(self):
        from accounts.api import google_oauth_callback_get

        state = generate_oauth_state(role=Role.RENTER, next_url="/rent")
        req = MockBoltRequest(query={"code": "mock-code", "state": state})

        fake_user_info = {
            "sub": "google-user-8888",
            "email": "get.test@example.com",
            "name": "Get Tester",
            "picture": "",
        }

        with patch("accounts.api.exchange_code_for_user_info", return_value=fake_user_info):
            res = await google_oauth_callback_get(req)
            self.assertEqual(res.status_code, 303)
            self.assertEqual(res.url, "http://localhost:4200/rent")


class EmailVerificationTests(TestCase):
    async def test_disposable_email_rejected(self):
        from accounts.email_verification import validate_real_email

        is_real, err = await validate_real_email("test@mailinator.com")
        self.assertFalse(is_real)
        self.assertEqual(err, "disposable_email_not_allowed")

        is_real, err = await validate_real_email("user@tempmail.com")
        self.assertFalse(is_real)
        self.assertEqual(err, "disposable_email_not_allowed")

    async def test_invalid_syntax_email_rejected(self):
        from accounts.email_verification import validate_real_email

        is_real, err = await validate_real_email("not-an-email")
        self.assertFalse(is_real)
        self.assertEqual(err, "invalid_email_format")

    async def test_real_domain_accepted(self):
        from accounts.email_verification import validate_real_email

        is_real, err = await validate_real_email("real.user@gmail.com")
        self.assertTrue(is_real)
        self.assertIsNone(err)

    async def test_create_and_verify_otp_flow(self):
        from accounts.email_verification import create_and_send_verification_otp

        record = await create_and_send_verification_otp(
            email="newtenant@gmail.com",
            payload={
                "full_name": "New Tenant",
                "username": "newtenant",
                "password": "securepassword",
                "role": Role.RENTER,
            },
        )
        self.assertEqual(len(record.code), 6)
        self.assertFalse(record.is_verified)
        self.assertFalse(record.is_expired)

    async def test_register_view_triggers_otp(self):
        import json
        from accounts.api import register_view
        from accounts.models import EmailVerification

        req = MockBoltRequest(
            body=json.dumps({
                "full_name": "Test Real User",
                "username": "testrealuser",
                "email": "testrealuser@gmail.com",
                "password": "mypassword123",
                "password_confirm": "mypassword123",
                "role": "renter",
            }).encode("utf-8")
        )

        res = await register_view(req)
        self.assertEqual(res["status"], "otp_required")
        self.assertEqual(res["email"], "testrealuser@gmail.com")

        record = await EmailVerification.objects.filter(
            email="testrealuser@gmail.com"
        ).afirst()
        self.assertIsNotNone(record)
        self.assertEqual(len(record.code), 6)

    async def test_verify_otp_creates_user(self):
        import json
        from accounts.api import register_verify_otp_view
        from accounts.email_verification import create_and_send_verification_otp

        record = await create_and_send_verification_otp(
            email="verifiedtenant@gmail.com",
            payload={
                "full_name": "Verified Tenant",
                "username": "verifiedtenant",
                "password": "securepassword123",
                "role": "renter",
            },
        )

        req = MockBoltRequest(
            body=json.dumps({
                "email": "verifiedtenant@gmail.com",
                "code": record.code,
            }).encode("utf-8")
        )

        res = await register_verify_otp_view(req)
        self.assertEqual(res["status"], "active")
        self.assertEqual(res["user"]["email"], "verifiedtenant@gmail.com")

        created_user = await User.objects.filter(
            email="verifiedtenant@gmail.com"
        ).afirst()
        self.assertIsNotNone(created_user)
        self.assertTrue(created_user.is_email_verified)
        self.assertTrue(created_user.is_active)

    async def test_verify_wrong_otp_fails(self):
        import json
        from django_bolt.exceptions import HTTPException
        from accounts.api import register_verify_otp_view
        from accounts.email_verification import create_and_send_verification_otp

        await create_and_send_verification_otp(
            email="wrongcode@gmail.com",
            payload={
                "full_name": "Wrong Code",
                "username": "wrongcode",
                "password": "securepassword123",
                "role": "renter",
            },
        )

        req = MockBoltRequest(
            body=json.dumps({
                "email": "wrongcode@gmail.com",
                "code": "000000",
            }).encode("utf-8")
        )

        with self.assertRaises(HTTPException) as ctx:
            await register_verify_otp_view(req)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_login_reports_pending_unverified_registration(self):
        import json
        from django_bolt.exceptions import HTTPException
        from accounts.api import login_view
        from accounts.email_verification import create_and_send_verification_otp

        await create_and_send_verification_otp(
            email="pendinglogin@gmail.com",
            payload={
                "full_name": "Pending Login",
                "username": "pendinglogin",
                "password": "securepassword123",
                "role": "renter",
            },
        )

        for identifier in ("pendinglogin@gmail.com", "pendinglogin"):
            req = MockBoltRequest(
                body=json.dumps(
                    {"identifier": identifier, "password": "securepassword123"}
                ).encode("utf-8")
            )
            with self.assertRaises(HTTPException) as ctx:
                await login_view(req)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(
                ctx.exception.detail,
                "registration_unverified:pendinglogin@gmail.com",
            )

    async def test_register_with_disposable_email_rejected(self):
        import json
        from django_bolt.exceptions import HTTPException
        from accounts.api import register_view

        req = MockBoltRequest(
            body=json.dumps({
                "full_name": "Disposable User",
                "username": "disposableuser",
                "email": "trash@mailinator.com",
                "password": "mypassword123",
                "password_confirm": "mypassword123",
                "role": "renter",
            }).encode("utf-8")
        )

        with self.assertRaises(HTTPException) as ctx:
            await register_view(req)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "disposable_email_not_allowed")

    async def test_re_registration_after_account_deletion(self):
        import json
        from accounts.api import register_view, register_verify_otp_view
        from accounts.email_verification import create_and_send_verification_otp

        email = "reregister_test@gmail.com"
        username = "reregtest"

        # 1. First registration and user creation
        record1 = await create_and_send_verification_otp(
            email=email,
            payload={
                "full_name": "First User",
                "username": username,
                "password": "Password123!",
                "role": Role.RENTER,
            },
        )
        req1 = MockBoltRequest(body=json.dumps({"email": email, "code": record1.code}).encode("utf-8"))
        res1 = await register_verify_otp_view(req1)
        self.assertEqual(res1["status"], "active")

        user1 = await User.objects.filter(email=email).afirst()
        self.assertIsNotNone(user1)
        user1_id = user1.id

        # 2. Account is deleted (e.g. by superadmin console)
        await user1.adelete()
        self.assertFalse(await User.objects.filter(email=email).aexists())

        # 3. User re-registers with the same email and username
        req_reg = MockBoltRequest(
            body=json.dumps({
                "full_name": "Second User Re-registered",
                "username": username,
                "email": email,
                "password": "NewPassword123!",
                "password_confirm": "NewPassword123!",
                "role": "renter",
            }).encode("utf-8")
        )
        res_reg = await register_view(req_reg)
        self.assertEqual(res_reg["status"], "otp_required")

        record2 = await EmailVerification.objects.filter(email=email, is_verified=False).afirst()
        self.assertIsNotNone(record2)

        # 4. Verify OTP for re-registered account
        req2 = MockBoltRequest(body=json.dumps({"email": email, "code": record2.code}).encode("utf-8"))
        res2 = await register_verify_otp_view(req2)
        self.assertEqual(res2["status"], "active")

        user2 = await User.objects.filter(email=email).afirst()
        self.assertIsNotNone(user2)
        self.assertNotEqual(user2.id, user1_id)
        self.assertEqual(user2.email, email)
        self.assertEqual(user2.username, username)
        self.assertEqual(user2.full_name, "Second User Re-registered")

    async def test_google_oauth_re_registration_after_account_deletion(self):
        user_info = {
            "sub": "google-deleted-recreated-sub",
            "email": "google_recreate@gmail.com",
            "name": "Google Recreate",
            "picture": "",
        }

        # 1. Initial Google sign in creates user
        user, created, block = await get_or_create_google_user(user_info, requested_role=Role.RENTER)
        self.assertTrue(created)
        self.assertIsNone(block)
        user_id = user.id

        # 2. Account is deleted
        await user.adelete()
        self.assertFalse(await User.objects.filter(email="google_recreate@gmail.com").aexists())

        # 3. User signs in with Google again using the same email
        user2, created2, block2 = await get_or_create_google_user(user_info, requested_role=Role.RENTER)
        self.assertTrue(created2)
        self.assertIsNone(block2)
        self.assertNotEqual(user2.id, user_id)
        self.assertEqual(user2.email, "google_recreate@gmail.com")

    async def test_google_oauth_new_user_prompts_role_selection_and_confirms(self):
        import json
        from accounts.api import google_oauth_callback_post, role_select_view
        from accounts.api import PENDING_ROLE_KEY

        user_info = {
            "sub": "google-unassigned-sub-123",
            "email": "fresh_google@gmail.com",
            "name": "Fresh Google User",
            "picture": "",
        }

        # 1. New user with no requested role -> requires role selection
        state = generate_oauth_state(role="", next_url="/rent")
        req = MockBoltRequest(
            body=json.dumps({"code": "mock-code", "state": state}).encode("utf-8")
        )

        with patch("accounts.api.exchange_code_for_user_info", return_value=user_info):
            res = await google_oauth_callback_post(req)
            self.assertEqual(res["status"], "select_role")
            self.assertEqual(res["redirect"], "/role-select")

        new_user = await User.objects.filter(email="fresh_google@gmail.com").afirst()
        self.assertIsNotNone(new_user)
        self.assertFalse(new_user.is_active)
        self.assertEqual(req.session[PENDING_ROLE_KEY], new_user.pk)

        # 2. User confirms their role as 'renter'
        req_role = MockBoltRequest(
            body=json.dumps({"role": "renter"}).encode("utf-8"),
            session=req.session,
        )
        res_role = await role_select_view(req_role)
        self.assertEqual(res_role["status"], "active")
        self.assertEqual(res_role["role"], "renter")
        self.assertEqual(res_role["home_url"], "/rent")

        updated_user = await User.objects.filter(email="fresh_google@gmail.com").afirst()
        self.assertEqual(updated_user.role, Role.RENTER)
        self.assertTrue(updated_user.is_active)
        self.assertEqual(updated_user.approval_status, ApprovalStatus.APPROVED)






