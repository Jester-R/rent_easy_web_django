"""Telegram sign-in helpers for RentEasy.

The primary flow is a bot deep link: the website creates a one-time token,
opens ``https://t.me/<bot>?start=<token>``, the bot replies with a 6-digit
code, and the website redeems it. The legacy Login Widget callback remains
for deployments that still use the widget.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from accounts.google_oauth import _generate_unique_username
from accounts.integration_config import (
    telegram_bot_token,
    telegram_bot_username,
    telegram_login_auth_url as configured_telegram_login_auth_url,
)
from accounts.models import (
    ApprovalStatus,
    Role,
    TelegramLoginRequest,
    User,
)
from core.bolt import in_thread

logger = logging.getLogger(__name__)

TELEGRAM_LOGIN_MAX_AGE = 600  # 10 minutes
TELEGRAM_LOGIN_REQUEST_TTL = 600  # 10 minutes
TELEGRAM_LOGIN_MAX_ATTEMPTS = 5
TELEGRAM_LOGIN_TOKEN_PREFIX = "tl_"
TELEGRAM_PROFILE_FIELDS = (
    "id",
    "first_name",
    "last_name",
    "username",
    "photo_url",
    "auth_date",
    "hash",
)


def is_telegram_login_configured() -> bool:
    """Return True when the bot token and public username are configured."""
    return bool(telegram_bot_token() and telegram_bot_username())


def telegram_bot_id() -> str:
    """Return the public numeric bot id used by the Telegram OAuth popup."""
    token = telegram_bot_token()
    return token.split(":", 1)[0] if ":" in token else ""


def telegram_login_auth_url() -> str:
    """URL Telegram redirects to after the user authorizes the widget."""
    default_url = (
        f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:4200').rstrip('/')}"
        "/api/auth/telegram/callback/"
    )
    return configured_telegram_login_auth_url() or default_url


def verify_telegram_login(data: dict[str, Any]) -> dict[str, str] | None:
    """Verify the HMAC hash and freshness of a Telegram Login Widget payload.

    Returns the verified payload, or ``None`` when the payload is incomplete,
    tampered with, or too old. See
    https://core.telegram.org/widgets/login#checking-authorization
    """
    token = telegram_bot_token()
    if not token:
        return None

    payload = {
        key: str(data.get(key) or "").strip()
        for key in TELEGRAM_PROFILE_FIELDS
        if data.get(key) is not None
    }
    received_hash = payload.pop("hash", "")
    if not received_hash or not payload.get("id") or not payload.get("auth_date"):
        return None

    check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    expected_hash = hmac.new(
        secret_key, check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning("Telegram login payload failed hash verification")
        return None

    try:
        auth_date = int(payload["auth_date"])
    except TypeError, ValueError:
        return None
    if time.time() - auth_date > TELEGRAM_LOGIN_MAX_AGE:
        logger.warning("Telegram login payload expired")
        return None

    return payload


def _apply_telegram_profile(user: User, full_name: str, avatar_url: str) -> list[str]:
    """Sync the Telegram profile without clobbering user-supplied data."""
    updates: list[str] = []

    current_name = (user.full_name or "").strip()
    incoming_name = (full_name or "").strip()
    placeholder_name = current_name.casefold() == (user.username or "").casefold()
    if incoming_name and (not current_name or placeholder_name):
        if current_name != incoming_name[:120]:
            user.full_name = incoming_name[:120]
            updates.append("full_name")

    current_avatar = (user.avatar_url or "").strip()
    incoming_avatar = (avatar_url or "").strip()
    if incoming_avatar and (
        not current_avatar or "t.me" in current_avatar or "telesco.pe" in current_avatar
    ):
        if current_avatar != incoming_avatar:
            user.avatar_url = incoming_avatar
            updates.append("avatar_url")

    return updates


def _create_telegram_user(
    *,
    email: str,
    username: str,
    full_name: str,
    avatar_url: str,
    telegram_id: str,
    role: str,
    is_active: bool,
    approval_status: str,
) -> User:
    """Create a Telegram-only account with an unusable password."""
    user = User(
        email=email.strip().lower(),
        username=username,
        full_name=full_name.strip()[:120],
        avatar_url=avatar_url,
        telegram_id=telegram_id,
        telegram_chat_id=telegram_id,
        role=role,
        is_active=is_active,
        approval_status=approval_status,
        is_email_verified=False,
    )
    user.set_unusable_password()
    user.save()
    return user


async def create_telegram_login_request(role: str = "") -> TelegramLoginRequest:
    """Create the browser-side half of a bot deep-link login."""
    requested_role = role if role in {Role.RENTER, Role.OWNER} else ""
    return await TelegramLoginRequest.objects.acreate(
        token=f"{TELEGRAM_LOGIN_TOKEN_PREFIX}{secrets.token_urlsafe(24)}",
        role=requested_role,
        expires_at=timezone.now() + timedelta(seconds=TELEGRAM_LOGIN_REQUEST_TTL),
    )


async def _generate_unique_telegram_login_code() -> str:
    now = timezone.now()
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        exists = await TelegramLoginRequest.objects.filter(
            code=code,
            consumed_at__isnull=True,
            expires_at__gt=now,
        ).aexists()
        if not exists:
            return code
    # A collision after 20 attempts is practically impossible; keep the
    # one-time code short rather than exposing the long-lived token.
    return f"{secrets.randbelow(1_000_000):06d}"


async def authorize_telegram_login_request(
    token: str,
    *,
    telegram_id: str,
    username: str = "",
    first_name: str = "",
    last_name: str = "",
    photo_url: str = "",
) -> TelegramLoginRequest | None:
    """Attach the Telegram identity from a bot ``/start <token>`` update."""
    login_request = await TelegramLoginRequest.objects.filter(
        token=token,
        consumed_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).afirst()
    if login_request is None:
        return None

    # The same deep link must not be redeemable by a second Telegram account.
    if login_request.telegram_id and login_request.telegram_id != telegram_id:
        return None

    login_request.telegram_id = telegram_id
    login_request.username = username[:64]
    login_request.first_name = first_name[:120]
    login_request.last_name = last_name[:120]
    login_request.photo_url = photo_url[:500]
    update_fields = [
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "photo_url",
    ]
    if not login_request.code:
        login_request.code = await _generate_unique_telegram_login_code()
        update_fields.append("code")
    await login_request.asave(update_fields=update_fields)
    return login_request


async def verify_telegram_login_code(
    token: str, code: str
) -> tuple[User, bool, str | None]:
    """Redeem the one-time code the bot sent and sign the user in."""
    login_request = await TelegramLoginRequest.objects.filter(
        token=token, consumed_at__isnull=True
    ).afirst()
    if login_request is None or login_request.is_expired:
        raise ValueError("code_expired")
    if not login_request.telegram_id or not login_request.code:
        raise ValueError("code_not_ready")
    if login_request.attempts >= TELEGRAM_LOGIN_MAX_ATTEMPTS:
        raise ValueError("too_many_attempts")

    submitted = (code or "").strip()
    if not hmac.compare_digest(login_request.code, submitted):
        login_request.attempts += 1
        await login_request.asave(update_fields=["attempts"])
        raise ValueError("invalid_code")

    login_request.consumed_at = timezone.now()
    await login_request.asave(update_fields=["consumed_at"])

    payload = {
        "id": login_request.telegram_id,
        "first_name": login_request.first_name,
        "last_name": login_request.last_name,
        "username": login_request.username,
        "photo_url": login_request.photo_url,
    }
    return await get_or_create_telegram_user(payload, requested_role=login_request.role)


async def _generate_unique_telegram_email(telegram_id: str) -> str:
    candidate = f"telegram_{telegram_id}@telegram.local"
    while await User.objects.filter(email__iexact=candidate).aexists():
        candidate = f"telegram_{telegram_id}_{secrets.token_hex(3)}@telegram.local"
    return candidate


async def get_or_create_telegram_user(
    payload: dict[str, Any], requested_role: str = ""
) -> tuple[User, bool, str | None]:
    """Find or create the RentEasy account behind a verified Telegram payload.

    Returns ``(user, created, error_detail)`` where ``error_detail`` is ``None``
    when the user may sign in immediately, or one of ``select_role``,
    ``approval_pending``, ``registration_rejected``, ``not_authorized``.
    """
    from accounts.api import _notify_admins_of_owner_request
    from accounts.models import PlatformSettings

    telegram_id = str(payload.get("id") or "").strip()
    if not telegram_id:
        raise ValueError("Telegram payload missing id")

    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    telegram_username = str(payload.get("username") or "").strip()
    avatar_url = str(payload.get("photo_url") or "").strip()

    # 1. Accounts created through the Telegram Login Widget.
    user = await User.objects.filter(telegram_id=telegram_id).afirst()

    # 2. Accounts linked earlier from the profile page (chat id == user id).
    if user is None:
        user = await User.objects.filter(telegram_chat_id=telegram_id).afirst()
        if user is not None:
            user.telegram_id = telegram_id
            updates = [
                "telegram_id",
                *_apply_telegram_profile(user, full_name, avatar_url),
            ]
            await user.asave(update_fields=updates)

    # 3. Existing account: keep the notification link in sync.
    if user is not None:
        if user.telegram_chat_id != telegram_id:
            user.telegram_chat_id = telegram_id
            await user.asave(update_fields=["telegram_chat_id"])

        if user.approval_status == ApprovalStatus.PENDING:
            return user, False, "approval_pending"
        if user.approval_status == ApprovalStatus.REJECTED:
            return user, False, "registration_rejected"
        if not user.is_active:
            return user, False, "not_authorized"
        return user, False, None

    # 4. New Telegram-only account.
    needs_role = requested_role not in {Role.RENTER, Role.OWNER}
    role = requested_role if not needs_role else Role.RENTER
    platform, _ = await PlatformSettings.objects.aget_or_create(pk=1)

    is_active = True
    approval_status = ApprovalStatus.APPROVED

    if needs_role:
        is_active = False
    elif role == Role.OWNER and not platform.auto_approve_owners:
        is_active = False
        approval_status = ApprovalStatus.PENDING

    email = await _generate_unique_telegram_email(telegram_id)
    username = await _generate_unique_username(full_name or telegram_username, email)

    user = await in_thread(
        _create_telegram_user,
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        telegram_id=telegram_id,
        role=role,
        is_active=is_active,
        approval_status=approval_status,
    )

    from accounts.account_notifications import (
        notify_account_created,
        notify_admins_of_telegram_registration,
    )

    await in_thread(notify_account_created, user, "Telegram")
    await in_thread(notify_admins_of_telegram_registration, user)

    if needs_role:
        return user, True, "select_role"

    if approval_status == ApprovalStatus.PENDING:
        await in_thread(_notify_admins_of_owner_request, user)
        return user, True, "approval_pending"

    return user, True, None
