"""Accounts JSON endpoints: auth, profile, rener/owner dashboards, and the
superadmin console (mounted from :mod:`accounts.console_api`).

Handlers are native async Django-Bolt handlers: ORM reads use the Django async
ORM and ``django.contrib.auth`` / manager / model helpers hop to a worker
thread via :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Annotated
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_bolt import BoltAPI, UploadFile
from django_bolt.exceptions import HTTPException
from django_bolt.params import File
from django_bolt.responses import Redirect

from accounts.email_verification import (
    RESEND_COOLDOWN_SECONDS,
    create_and_send_verification_otp,
    validate_real_email,
)
from accounts.google_oauth import (
    exchange_code_for_user_info,
    get_authorization_url,
    get_or_create_google_user,
    is_google_oauth_configured,
    verify_oauth_state,
)
from accounts.models import (
    ApprovalStatus,
    AuditLog,
    EmailVerification,
    PlatformSettings,
    Role,
    User,
    is_valid_username,
    normalize_identity,
)
from accounts.payouts import apply_payout_fields
from accounts.telegram_login import (
    TELEGRAM_LOGIN_REQUEST_TTL,
    TELEGRAM_LOGIN_TOKEN_PREFIX,
    authorize_telegram_login_request,
    create_telegram_login_request,
    get_or_create_telegram_user,
    is_telegram_login_configured,
    telegram_bot_id,
    telegram_login_auth_url,
    verify_telegram_login,
    verify_telegram_login_code,
)
from notifications.models import Notification
from notifications.services import notify
from bookings.models import Booking, BookingStatus
from core.bolt import (
    body_str,
    in_thread,
    json_body,
    mark_full_request,
    owner_required,
    q,
    query,
    renter_required,
    session_get,
    session_pop,
    session_set,
)
from core.bolt import login_required as require_login
from core.bolt_serializers import booking as serialize_booking
from core.bolt_serializers import payment as serialize_payment
from core.bolt_serializers import property as serialize_property
from core.bolt_serializers import user as serialize_user
from core.uploads import MAX_IMAGE_BYTES, delete_image_url, save_image
from listings.models import Favorite, Property
from payments.models import Payment

logger = logging.getLogger(__name__)

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)

PENDING_ROLE_KEY = "renteasy_pending_role_user"
FLASH_KEY = "renteasy_flash"


async def _flash(request, key: str) -> None:
    await session_set(request, FLASH_KEY, key)


def _approval_block_detail(identifier: str, password: str) -> str | None:
    """Explain why an inactive account cannot sign in (Django's ``authenticate``
    rejects inactive users before we can inspect ``approval_status``)."""
    user = (
        User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        )
        .order_by("id")
        .first()
    )
    if user is None or not user.check_password(password):
        return None
    if user.approval_status == ApprovalStatus.PENDING:
        return "approval_pending"
    if user.approval_status == ApprovalStatus.REJECTED:
        return "registration_rejected"
    if not user.is_active:
        return "not_authorized"
    return None


def _notify_admins_of_owner_request(owner: User) -> None:
    """Alert every superadmin/staff account that an owner awaits approval."""
    admins = User.objects.filter(
        Q(role=Role.SUPERADMIN) | Q(is_superuser=True) | Q(is_staff=True)
    ).distinct()
    for admin in admins:
        if admin.pk == owner.pk:
            continue
        notify(
            admin,
            Notification.Kind.OWNER_APPROVAL_REQUEST,
            "notif_owner_request",
            "notif_owner_request_body",
            params={"name": owner.display_name, "email": owner.email},
            link="/console/users/",
            action="owner_approval",
        )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@api.get("/auth/login/")
async def login_state(request):
    from core.bolt import get_user

    user = await get_user(request)
    if user is not None:
        return {"authenticated": True, "user": await serialize_user(user)}
    return {"authenticated": False}


@api.post("/auth/login/")
async def login_view(request):
    data = json_body(request)
    identifier = normalize_identity(
        body_str(data, "identifier") or body_str(data, "email")
    )
    password = body_str(data, "password")
    if not identifier or not password:
        raise HTTPException(status_code=422, detail="credentials_required")

    user = await in_thread(
        authenticate, request, username=identifier, password=password
    )
    if user is None:
        block = await in_thread(_approval_block_detail, identifier, password)
        if block:
            raise HTTPException(status_code=403, detail=block)

        # Check if user registered but hasn't completed email OTP verification yet
        pending_reg = (
            await EmailVerification.objects.filter(
                Q(email__iexact=identifier) | Q(payload__username__iexact=identifier),
                purpose=EmailVerification.Purpose.REGISTER,
                is_verified=False,
            )
            .order_by("-created_at")
            .afirst()
        )
        if pending_reg:
            raise HTTPException(
                status_code=403,
                detail=f"registration_unverified:{pending_reg.email}",
            )

        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="not_authorized")
    if not getattr(user, "is_email_verified", True):
        raise HTTPException(status_code=403, detail="email_not_verified")

    await in_thread(login, request, user)
    await in_thread(user.touch_login)

    destination = body_str(data, "next") or user.home_url
    if not destination.startswith("/"):
        destination = user.home_url
    return {
        "user": await serialize_user(user),
        "home_url": user.home_url,
        "redirect": destination,
    }


@api.post("/auth/register/")
async def register_view(request):
    data = json_body(request)
    full_name = body_str(data, "full_name")
    username = body_str(data, "username")
    email = normalize_identity(body_str(data, "email"))
    password = body_str(data, "password")
    confirm = body_str(data, "password_confirm")
    role = body_str(data, "role") or Role.RENTER

    if not email:
        raise HTTPException(status_code=422, detail="email_required")
    if not password:
        raise HTTPException(status_code=422, detail="password_required")
    if password != confirm:
        raise HTTPException(status_code=422, detail="password_mismatch")
    if not is_valid_username(username):
        raise HTTPException(status_code=422, detail="username_invalid")
    if role not in {Role.RENTER, Role.OWNER}:
        raise HTTPException(status_code=422, detail="invalid_role")
    if await User.objects.filter(email__iexact=email).aexists():
        raise HTTPException(status_code=409, detail="email_taken")
    if await User.objects.filter(username__iexact=username).aexists():
        raise HTTPException(status_code=409, detail="username_taken")

    # Real email & disposable/fake domain verification
    is_real, err_detail = await validate_real_email(email)
    if not is_real:
        raise HTTPException(
            status_code=422, detail=err_detail or "invalid_email_format"
        )

    # Create and send 6-digit OTP verification email
    payload = {
        "full_name": full_name,
        "username": username,
        "email": email,
        "password": password,
        "role": role,
    }
    await create_and_send_verification_otp(
        email=email,
        payload=payload,
        purpose=EmailVerification.Purpose.REGISTER,
    )

    return {
        "status": "otp_required",
        "email": email,
        "role": role,
        "message": "otp_sent",
    }


@api.post("/auth/register/verify-otp/")
async def register_verify_otp_view(request):
    data = json_body(request)
    email = normalize_identity(body_str(data, "email"))
    code = body_str(data, "code").strip()

    if not email or not code:
        raise HTTPException(status_code=422, detail="otp_credentials_required")

    record = (
        await EmailVerification.objects.filter(
            email__iexact=email,
            purpose=EmailVerification.Purpose.REGISTER,
            is_verified=False,
        )
        .order_by("-created_at")
        .afirst()
    )

    if record is None or record.is_expired:
        raise HTTPException(status_code=400, detail="otp_expired_or_invalid")

    if record.attempts >= 5:
        raise HTTPException(status_code=429, detail="too_many_attempts")

    if record.code != code:
        record.attempts += 1
        await record.asave(update_fields=["attempts"])
        remaining = max(0, 5 - record.attempts)
        raise HTTPException(
            status_code=400,
            detail=f"invalid_otp_code:{remaining}",
        )

    # Valid OTP confirmation
    record.is_verified = True
    await record.asave(update_fields=["is_verified"])

    payload = record.payload or {}
    full_name = payload.get("full_name", "")
    username = payload.get("username", "")
    password = payload.get("password", "")
    role = payload.get("role", Role.RENTER)

    if await User.objects.filter(email__iexact=email).aexists():
        raise HTTPException(status_code=409, detail="email_taken")
    if await User.objects.filter(username__iexact=username).aexists():
        raise HTTPException(status_code=409, detail="username_taken")

    settings_obj, _ = await PlatformSettings.objects.aget_or_create(pk=1)

    if role == Role.OWNER and not settings_obj.auto_approve_owners:
        user = await in_thread(
            User.objects.create_user,
            email=email,
            username=username,
            password=password,
            full_name=full_name,
            role=Role.OWNER,
            is_active=False,
            approval_status=ApprovalStatus.PENDING,
            is_email_verified=True,
        )
        await in_thread(_notify_admins_of_owner_request, user)
        return {
            "status": "pending_approval",
            "role": Role.OWNER,
            "message": "approval_pending",
            "redirect": "/login/",
        }

    user = await in_thread(
        User.objects.create_user,
        email=email,
        username=username,
        password=password,
        full_name=full_name,
        role=role,
        is_email_verified=True,
    )
    await in_thread(login, request, user)
    return {
        "status": "active",
        "user": await serialize_user(user),
        "home_url": user.home_url,
        "redirect": user.home_url,
    }


@api.post("/auth/register/resend-otp/")
async def register_resend_otp_view(request):
    data = json_body(request)
    email = normalize_identity(body_str(data, "email"))
    if not email:
        raise HTTPException(status_code=422, detail="email_required")

    record = (
        await EmailVerification.objects.filter(
            email__iexact=email,
            purpose=EmailVerification.Purpose.REGISTER,
        )
        .order_by("-created_at")
        .afirst()
    )

    if record is None:
        raise HTTPException(status_code=404, detail="no_pending_registration")

    time_since_last = (timezone.now() - record.created_at).total_seconds()
    if time_since_last < RESEND_COOLDOWN_SECONDS:
        remaining = int(RESEND_COOLDOWN_SECONDS - time_since_last)
        raise HTTPException(status_code=429, detail=f"resend_cooldown:{remaining}")

    await create_and_send_verification_otp(
        email=email,
        payload=record.payload,
        purpose=EmailVerification.Purpose.REGISTER,
    )

    return {"ok": True, "message": "otp_resent"}


@api.post("/auth/role/")
async def role_select_view(request):
    data = json_body(request)
    pending_id = await session_get(request, PENDING_ROLE_KEY)
    if not pending_id:
        raise HTTPException(status_code=409, detail="no_pending_registration")

    user = await User.objects.filter(pk=pending_id).afirst()
    if user is None:
        await session_pop(request, PENDING_ROLE_KEY, None)
        raise HTTPException(status_code=404, detail="pending_user_missing")

    role = body_str(data, "role")
    if role not in {Role.RENTER, Role.OWNER}:
        raise HTTPException(status_code=422, detail="select_role_hint")

    platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)
    user.role = role
    if role == Role.OWNER and not platform.auto_approve_owners:
        user.is_active = False
        user.approval_status = ApprovalStatus.PENDING
        await user.asave(update_fields=["role", "is_active", "approval_status"])
        await in_thread(_notify_admins_of_owner_request, user)
        await AuditLog.objects.acreate(
            actor=user,
            action=AuditLog.Action.UPDATE,
            entity="user",
            entity_id=str(user.pk),
            summary="owner registration pending approval",
        )
        await session_pop(request, PENDING_ROLE_KEY, None)
        return {
            "ok": True,
            "status": "pending_approval",
            "role": role,
            "redirect": "/register?pending=1",
        }
    user.is_active = True
    user.approval_status = ApprovalStatus.APPROVED
    await user.asave(update_fields=["role", "is_active", "approval_status"])
    await in_thread(login, request, user)
    await in_thread(user.touch_login)
    await AuditLog.objects.acreate(
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity="user",
        entity_id=str(user.pk),
        summary=f"role set to {user.role}",
    )
    await session_pop(request, PENDING_ROLE_KEY, None)
    await _flash(request, "registration_complete")
    return {
        "ok": True,
        "status": "active",
        "user": await serialize_user(user),
        "role": role,
        "home_url": user.home_url,
        "redirect": user.home_url,
    }


@api.post("/auth/logout/")
async def logout_view(request):
    from core.bolt import get_user

    user = await get_user(request)
    await AuditLog.objects.acreate(
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity="session",
        entity_id=str(user.pk) if user else "",
        summary="logout",
    )
    await in_thread(logout, request)
    return {"ok": True, "redirect": "/login/"}


# ---------------------------------------------------------------------------
# Google OAuth 2.0
# ---------------------------------------------------------------------------


@api.get("/auth/google/config/")
async def google_oauth_config_view(request):
    configured = is_google_oauth_configured()
    return {
        "enabled": configured,
        "client_id": (
            getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") if configured else ""
        ),
    }


@api.get("/auth/google/url/")
async def google_oauth_url_view(request):
    if not is_google_oauth_configured():
        return {"enabled": False, "url": ""}
    role = q(request, "role", "")
    next_url = q(request, "next", "")
    redirect_uri = q(request, "redirect_uri", "")
    try:
        url = get_authorization_url(
            role=role, next_url=next_url, redirect_uri=redirect_uri
        )
        return {"enabled": True, "url": url}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@api.get("/auth/google/login/")
async def google_oauth_login_view(request):
    frontend_base = getattr(
        settings, "FRONTEND_BASE_URL", "http://localhost:4200"
    ).rstrip("/")
    if not is_google_oauth_configured():
        return Redirect(
            f"{frontend_base}/login?error=oauth_not_configured", status_code=303
        )

    role = q(request, "role", "")
    next_url = q(request, "next", "")
    redirect_uri = q(request, "redirect_uri", "")
    try:
        url = get_authorization_url(
            role=role, next_url=next_url, redirect_uri=redirect_uri
        )
        return Redirect(url, status_code=303)
    except Exception as exc:
        logger.error("Failed to generate Google auth URL: %s", exc)
        return Redirect(f"{frontend_base}/login?error=oauth_failed", status_code=303)


@api.get("/auth/google/callback/")
async def google_oauth_callback_get(request):
    frontend_base = getattr(
        settings, "FRONTEND_BASE_URL", "http://localhost:4200"
    ).rstrip("/")

    error = q(request, "error", "")
    if error:
        return Redirect(f"{frontend_base}/login?error=oauth_cancelled", status_code=303)

    code = q(request, "code", "")
    state = q(request, "state", "")
    if not code or not state:
        return Redirect(
            f"{frontend_base}/login?error=oauth_missing_parameters", status_code=303
        )

    state_data = verify_oauth_state(state)
    if not state_data:
        return Redirect(
            f"{frontend_base}/login?error=oauth_invalid_state", status_code=303
        )

    role = state_data.get("role") or ""
    next_url = state_data.get("next") or ""
    redirect_uri = state_data.get("redirect_uri") or ""

    try:
        user_info = await exchange_code_for_user_info(code, redirect_uri=redirect_uri)
    except Exception as exc:
        logger.error("Failed exchanging Google auth code: %s", exc)
        return Redirect(
            f"{frontend_base}/login?error=oauth_exchange_failed", status_code=303
        )

    try:
        user, created, block = await get_or_create_google_user(
            user_info, requested_role=role
        )
    except Exception as exc:
        logger.error("Failed getting/creating Google user: %s", exc)
        return Redirect(
            f"{frontend_base}/login?error=oauth_account_failed", status_code=303
        )

    if block:
        if block == "select_role":
            await session_set(request, PENDING_ROLE_KEY, user.pk)
            return Redirect(f"{frontend_base}/role-select", status_code=303)
        if block == "approval_pending":
            return Redirect(f"{frontend_base}/register?pending=1", status_code=303)
        return Redirect(f"{frontend_base}/login?error={block}", status_code=303)

    await in_thread(login, request, user)
    await in_thread(user.touch_login)

    destination = next_url if (next_url and next_url.startswith("/")) else user.home_url
    return Redirect(f"{frontend_base}{destination}", status_code=303)


@api.post("/auth/google/callback/")
async def google_oauth_callback_post(request):
    data = json_body(request)
    code = body_str(data, "code")
    state = body_str(data, "state")
    redirect_uri = body_str(data, "redirect_uri")

    if not code:
        raise HTTPException(status_code=422, detail="code_required")

    role = ""
    next_url = ""
    if state:
        state_data = verify_oauth_state(state)
        if not state_data:
            raise HTTPException(status_code=400, detail="invalid_oauth_state")
        role = state_data.get("role") or ""
        next_url = state_data.get("next") or ""
        if not redirect_uri:
            redirect_uri = state_data.get("redirect_uri") or ""

    try:
        user_info = await exchange_code_for_user_info(code, redirect_uri=redirect_uri)
    except Exception as exc:
        logger.error("Failed exchanging Google auth code: %s", exc)
        raise HTTPException(status_code=400, detail="token_exchange_failed")

    try:
        user, created, block = await get_or_create_google_user(
            user_info, requested_role=role
        )
    except Exception as exc:
        logger.error("Failed creating/linking Google user: %s", exc)
        raise HTTPException(status_code=400, detail="account_creation_failed")

    if block:
        if block == "select_role":
            await session_set(request, PENDING_ROLE_KEY, user.pk)
            return {
                "ok": True,
                "status": "select_role",
                "redirect": "/role-select",
            }
        if block == "approval_pending":
            return {
                "status": "pending_approval",
                "role": user.role,
                "message": "approval_pending",
                "redirect": "/register?pending=1",
            }
        raise HTTPException(status_code=403, detail=block)

    await in_thread(login, request, user)
    await in_thread(user.touch_login)

    destination = next_url if (next_url and next_url.startswith("/")) else user.home_url
    return {
        "ok": True,
        "status": "active",
        "user": await serialize_user(user),
        "home_url": user.home_url,
        "redirect": destination,
    }


# ---------------------------------------------------------------------------
# Telegram sign-in (bot deep link + legacy Login Widget callback)
# ---------------------------------------------------------------------------


@api.get("/auth/telegram/config/")
async def telegram_login_config_view(request):
    enabled = is_telegram_login_configured()
    return {
        "enabled": enabled,
        "bot_username": (
            getattr(settings, "TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
            if enabled
            else ""
        ),
        "bot_id": telegram_bot_id() if enabled else "",
        "auth_url": telegram_login_auth_url() if enabled else "",
    }


@api.post("/auth/telegram/login/start/")
async def telegram_login_start(request):
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    if not is_telegram_login_configured() or not bot_username:
        raise HTTPException(status_code=503, detail="telegram_not_configured")

    data = json_body(request)
    login_request = await create_telegram_login_request(body_str(data, "role") or "")
    return {
        "token": login_request.token,
        "url": f"https://t.me/{bot_username}?start={login_request.token}",
        "expires_in": TELEGRAM_LOGIN_REQUEST_TTL,
    }


@api.post("/auth/telegram/login/verify/")
async def telegram_login_verify(request):
    data = json_body(request)
    token = body_str(data, "token")
    code = body_str(data, "code")
    if not token or not code:
        raise HTTPException(status_code=422, detail="code_required")

    try:
        user, _created, block = await verify_telegram_login_code(token, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if block:
        if block == "select_role":
            await session_set(request, PENDING_ROLE_KEY, user.pk)
            return {
                "ok": True,
                "status": "select_role",
                "redirect": "/role-select",
            }
        if block == "approval_pending":
            return {
                "ok": True,
                "status": "pending_approval",
                "redirect": "/register?pending=1",
            }
        raise HTTPException(status_code=403, detail=block)

    await in_thread(login, request, user)
    await in_thread(user.touch_login)
    return {
        "ok": True,
        "status": "active",
        "user": await serialize_user(user),
        "home_url": user.home_url,
        "redirect": user.home_url,
    }


@api.get("/auth/telegram/callback/")
async def telegram_login_callback(request):
    frontend_base = getattr(
        settings, "FRONTEND_BASE_URL", "http://localhost:4200"
    ).rstrip("/")
    if not is_telegram_login_configured():
        return Redirect(
            f"{frontend_base}/login?error=telegram_not_configured", status_code=303
        )

    received = query(request)
    payload = {
        key: received[key]
        for key in (
            "id",
            "first_name",
            "last_name",
            "username",
            "photo_url",
            "auth_date",
            "hash",
        )
        if key in received
    }
    verified = verify_telegram_login(payload)
    if verified is None:
        return Redirect(
            f"{frontend_base}/login?error=telegram_invalid", status_code=303
        )

    role = q(request, "role", "")
    next_url = q(request, "next", "")

    try:
        user, _created, block = await get_or_create_telegram_user(
            verified, requested_role=role
        )
    except Exception as exc:
        logger.error("Failed getting/creating Telegram user: %s", exc)
        return Redirect(
            f"{frontend_base}/login?error=telegram_account_failed", status_code=303
        )

    if block:
        if block == "select_role":
            await session_set(request, PENDING_ROLE_KEY, user.pk)
            return Redirect(f"{frontend_base}/role-select", status_code=303)
        if block == "approval_pending":
            return Redirect(f"{frontend_base}/register?pending=1", status_code=303)
        return Redirect(f"{frontend_base}/login?error={block}", status_code=303)

    await in_thread(login, request, user)
    await in_thread(user.touch_login)

    destination = next_url if (next_url and next_url.startswith("/")) else user.home_url
    return Redirect(f"{frontend_base}{destination}", status_code=303)


# ---------------------------------------------------------------------------
# Profile + preferences
# ---------------------------------------------------------------------------


@api.post("/auth/avatar/")
async def avatar_upload(
    request,
    avatar: Annotated[
        UploadFile,
        File(
            max_size=MAX_IMAGE_BYTES,
            allowed_types=["image/jpeg", "image/png", "image/webp", "image/gif"],
        ),
    ],
):
    user = await require_login(request)
    data = await avatar.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="image_too_large")
    try:
        url = await in_thread(save_image, data, f"avatars/{user.pk}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    previous = user.avatar_url
    user.avatar_url = url
    await user.asave(update_fields=["avatar_url"])
    if previous and previous != url:
        await in_thread(delete_image_url, previous)
    return {"user": await serialize_user(user), "url": url}


@api.get("/auth/preferences/")
async def profile_get(request):
    user = await require_login(request)
    return {"user": await serialize_user(user)}


@api.post("/auth/preferences/")
async def profile_update(request):
    user = await require_login(request)
    data = json_body(request)

    full_name = body_str(data, "full_name")
    username = body_str(data, "username")
    email = normalize_identity(body_str(data, "email"))

    if (
        email
        and await User.objects.filter(email__iexact=email).exclude(pk=user.pk).aexists()
    ):
        raise HTTPException(status_code=409, detail="email_taken")
    if username:
        if not is_valid_username(username):
            raise HTTPException(status_code=422, detail="username_invalid")
        if (
            await User.objects.filter(username__iexact=username)
            .exclude(pk=user.pk)
            .aexists()
        ):
            raise HTTPException(status_code=409, detail="username_taken")

    if "full_name" in data:
        user.full_name = full_name
    if email:
        user.email = email
    if username:
        user.username = username
    if "avatar_url" in data:
        avatar_url = body_str(data, "avatar_url")
        if avatar_url.startswith("data:") and (
            len(avatar_url) > 2_800_000
            or not avatar_url.startswith(
                (
                    "data:image/jpeg;base64,",
                    "data:image/png;base64,",
                    "data:image/webp;base64,",
                    "data:image/gif;base64,",
                )
            )
        ):
            raise HTTPException(status_code=422, detail="invalid_avatar_image")
        user.avatar_url = avatar_url
    payment_fields = ("payment_account_name", "payment_account_number", "payment_phone")
    if any(field in data for field in payment_fields):
        if user.role != Role.RENTER:
            raise HTTPException(status_code=403, detail="renter_required")
        user.payment_account_name = body_str(data, "payment_account_name").strip()[:120]
        user.payment_account_number = body_str(data, "payment_account_number").strip()[
            :64
        ]
        user.payment_phone = body_str(data, "payment_phone").strip()[:32]
    apply_payout_fields(user, data)
    await user.asave()
    await _flash(request, "account_updated")
    return {"user": await serialize_user(user)}


@api.post("/auth/telegram/link/")
async def telegram_link_create(request):
    user = await require_login(request)
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    if not bot_username:
        raise HTTPException(status_code=503, detail="telegram_bot_not_configured")
    user.telegram_link_token = secrets.token_urlsafe(24)
    user.telegram_link_expires_at = timezone.now() + timedelta(minutes=10)
    await user.asave(update_fields=["telegram_link_token", "telegram_link_expires_at"])
    return {"url": f"https://t.me/{bot_username}?start={user.telegram_link_token}"}


@api.post("/auth/telegram/unlink/")
async def telegram_unlink(request):
    user = await require_login(request)
    user.telegram_chat_id = ""
    user.telegram_link_token = ""
    user.telegram_link_expires_at = None
    await user.asave(
        update_fields=[
            "telegram_chat_id",
            "telegram_link_token",
            "telegram_link_expires_at",
        ]
    )
    return {"user": await serialize_user(user)}


@api.post("/telegram/webhook/")
async def telegram_webhook(request):
    expected_secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    supplied_secret = ""
    for header_name, header_value in request.headers.items():
        if header_name.lower() == "x-telegram-bot-api-secret-token":
            supplied_secret = header_value
            break
    if not expected_secret or not secrets.compare_digest(
        supplied_secret, expected_secret
    ):
        raise HTTPException(status_code=403, detail="invalid_webhook_secret")

    update = json_body(request)
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    text = str(message.get("text") or "")
    parts = text.split(maxsplit=1)
    if (
        chat.get("type") != "private"
        or not chat_id
        or not parts
        or parts[0] != "/start"
    ):
        return {"ok": True}

    from notifications.telegram import send_telegram_message

    token = parts[1].strip().split()[0] if len(parts) == 2 and parts[1].strip() else ""
    if not token:
        await in_thread(
            send_telegram_message,
            chat_id,
            "Open RentEasy, tap the blue Telegram icon, and press Start "
            "to receive a sign-in code.",
        )
        return {"ok": True}

    login_request = await authorize_telegram_login_request(
        token,
        telegram_id=chat_id,
        username=str(message.get("from", {}).get("username") or ""),
        first_name=str(message.get("from", {}).get("first_name") or ""),
        last_name=str(message.get("from", {}).get("last_name") or ""),
    )
    if login_request is not None:
        await in_thread(
            send_telegram_message,
            chat_id,
            "Your RentEasy login code is "
            f"{login_request.code}\n\n"
            "Enter it on the website to finish signing in. "
            "The code expires in 10 minutes.",
        )
        return {"ok": True}

    if token.startswith(TELEGRAM_LOGIN_TOKEN_PREFIX):
        await in_thread(
            send_telegram_message,
            chat_id,
            "This Telegram sign-in link is invalid or expired. "
            "Go back to RentEasy and tap the Telegram icon again.",
        )
        return {"ok": True}

    user = await User.objects.filter(
        telegram_link_token=token,
        telegram_link_expires_at__gt=timezone.now(),
    ).afirst()
    if user is None:
        await in_thread(
            send_telegram_message,
            chat_id,
            "This account link is invalid or expired. Please create a new link from your RentEasy profile.",
        )
        return {"ok": True}

    linked_elsewhere = (
        await User.objects.filter(telegram_chat_id=chat_id)
        .exclude(pk=user.pk)
        .aexists()
    )
    if linked_elsewhere:
        await in_thread(
            send_telegram_message,
            chat_id,
            "This Telegram account is already linked to another RentEasy account. Unlink it there first.",
        )
        return {"ok": True}

    user.telegram_chat_id = chat_id
    user.telegram_link_token = ""
    user.telegram_link_expires_at = None
    await user.asave(
        update_fields=[
            "telegram_chat_id",
            "telegram_link_token",
            "telegram_link_expires_at",
        ]
    )
    await in_thread(
        send_telegram_message,
        chat_id,
        "Your RentEasy account is connected. Booking and payment updates will be sent here.",
    )
    return {"ok": True}


@api.get("/auth/denied/")
async def deny(request):
    raise HTTPException(
        status_code=403,
        detail=f"role_required:{q(request, 'role') or 'unknown'}",
    )


@api.post("/theme/set/")
async def set_theme_view(request):
    data = json_body(request)
    theme = (body_str(data, "theme") or q(request, "theme")).strip().lower()
    if theme not in {"light", "dark"}:
        raise HTTPException(status_code=422, detail="unsupported_theme")
    await session_set(request, "renteasy_theme", theme)
    return {"ok": True, "theme": theme}


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------


@api.get("/rent/")
async def renter_dashboard(request):
    user = await renter_required(request)
    properties = (
        Property.objects.filter(owner__role=Role.OWNER)
        .for_renter(user)
        .order_by("-created_at")
    )
    bookings = (
        Booking.objects.filter(renter=user)
        .select_related("property", "owner", "payment", "payment__payout")
        .order_by("-created_at")
    )
    payments = (
        Payment.objects.select_related("property", "booking", "user")
        .filter(user=user)
        .order_by("-created_at")
    )
    favorites = Favorite.objects.filter(user=user).select_related("property")

    counts = {
        row["status"]: row["n"]
        async for row in bookings.values("status").annotate(n=Count("id"))
    }
    spend = (
        await payments.filter(status=Payment.Status.SUCCESS).aaggregate(v=Sum("amount"))
    )["v"] or 0
    refunded = (await payments.aaggregate(v=Sum("refunded_amount")))["v"] or 0

    suggested = properties.for_renter(user)[:6]
    favorite_ids = {v async for v in favorites.values_list("property_id", flat=True)}

    return {
        "stats": {
            "available": await Property.objects.filter(owner__role=Role.OWNER)
            .for_renter(user)
            .acount(),
            "bookings": await bookings.acount(),
            "active": counts.get(BookingStatus.PENDING, 0)
            + counts.get(BookingStatus.APPROVED, 0)
            + counts.get(BookingStatus.CONFIRMED, 0),
            "pending": counts.get(BookingStatus.PENDING, 0),
            "approved": counts.get(BookingStatus.APPROVED, 0)
            + counts.get(BookingStatus.CONFIRMED, 0),
            "favorites": await favorites.acount(),
            "payments": await payments.acount(),
            "spend": float(spend),
            "refunded": float(refunded),
        },
        "featured": [await serialize_property(p) async for p in properties[:3]],
        "suggested": [
            await serialize_property(p, is_favorite=p.pk in favorite_ids)
            async for p in suggested
        ],
        "recent_bookings": [await serialize_booking(b) async for b in bookings[:5]],
        "recent_payments": [await serialize_payment(p) async for p in payments[:5]],
        "favorite_ids": sorted(favorite_ids),
    }


@api.get("/owner/")
async def owner_dashboard(request):
    user = await owner_required(request)
    properties = (
        Property.objects.filter(owner=user)
        .select_related("owner")
        .annotate(
            favorite_count=Count("favorites", distinct=True),
            booking_count=Count("bookings", distinct=True),
            revenue=Sum(
                "payments__amount", filter=Q(payments__status=Payment.Status.SUCCESS)
            ),
        )
        .order_by("-created_at")
    )
    bookings = (
        Booking.objects.filter(owner=user)
        .select_related("property", "renter", "payment", "payment__payout")
        .order_by("-created_at")
    )
    payments = (
        Payment.objects.select_related("property", "booking", "user")
        .filter(property__owner=user)
        .order_by("-created_at")
    )

    counts = {
        row["status"]: row["n"]
        async for row in bookings.values("status").annotate(n=Count("id"))
    }
    potential = (await properties.aaggregate(v=Sum("price_per_month")))["v"] or 0
    revenue = (
        await payments.filter(status=Payment.Status.SUCCESS).aaggregate(v=Sum("amount"))
    )["v"] or 0
    favorites = await Favorite.objects.filter(property__owner=user).acount()

    return {
        "stats": {
            "listings": await properties.acount(),
            "pending": counts.get(BookingStatus.PENDING, 0),
            "approved": counts.get(BookingStatus.APPROVED, 0)
            + counts.get(BookingStatus.CONFIRMED, 0),
            "rejected": counts.get(BookingStatus.REJECTED, 0),
            "cancelled": counts.get(BookingStatus.CANCELLED, 0),
            "potential": float(potential),
            "revenue": float(revenue),
            "favorites": favorites,
            "bookings": await bookings.acount(),
            "payments": await payments.acount(),
        },
        "properties": [await serialize_property(p) async for p in properties],
        "recent_bookings": [await serialize_booking(b) async for b in bookings[:5]],
        "recent_payments": [await serialize_payment(p) async for p in payments[:5]],
    }


from accounts.console_api import console_api

api.mount("/console", console_api)


mark_full_request(api)

__all__ = ["api"]
