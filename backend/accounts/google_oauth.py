"""Google OAuth 2.0 helper functions for RentEasy."""

from __future__ import annotations

import logging
import re
import secrets
import urllib.parse
from typing import Any

import httpx
from django.conf import settings
from django.core import signing

from accounts.integration_config import (
    google_oauth_client_id,
    google_oauth_client_secret,
    google_oauth_redirect_uri,
)
from accounts.models import ApprovalStatus, Role, User
from core.bolt import in_thread

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

STATE_SALT = "renteasy-google-oauth-state"
STATE_MAX_AGE = 600  # 10 minutes


def is_google_oauth_configured() -> bool:
    """Return True if Google OAuth2 client credentials are configured."""
    return bool(google_oauth_client_id() and google_oauth_client_secret())


def generate_oauth_state(
    role: str = "", next_url: str = "", redirect_uri: str = ""
) -> str:
    """Create a tamper-proof signed state token containing session intent."""
    normalized_role = role if role in {Role.RENTER, Role.OWNER} else ""
    data = {
        "role": normalized_role,
        "next": next_url if (next_url and next_url.startswith("/")) else "",
        "redirect_uri": redirect_uri
        or getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", ""),
        "nonce": secrets.token_hex(16),
    }
    return signing.dumps(data, salt=STATE_SALT)


def verify_oauth_state(state: str) -> dict[str, Any] | None:
    """Verify and decode a signed OAuth state token. Returns None if invalid or expired."""
    if not state:
        return None
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
        if isinstance(data, dict):
            return data
    except signing.BadSignature, signing.SignatureExpired:
        logger.warning("Invalid or expired OAuth state token received")
    return None


def get_authorization_url(
    role: str = "", next_url: str = "", redirect_uri: str = ""
) -> str:
    """Build the Google OAuth2 authorization URL."""
    client_id = google_oauth_client_id()
    if not client_id:
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID is not configured")

    target_redirect_uri = (
        redirect_uri
        or google_oauth_redirect_uri()
        or f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:4200')}/api/auth/google/callback/"
    )

    state = generate_oauth_state(
        role=role, next_url=next_url, redirect_uri=target_redirect_uri
    )

    params = {
        "client_id": client_id,
        "redirect_uri": target_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_user_info(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code with Google for tokens and fetch profile info."""
    client_id = await in_thread(google_oauth_client_id)
    client_secret = await in_thread(google_oauth_client_secret)
    if not client_id or not client_secret:
        raise ValueError("Google OAuth credentials are not configured")

    target_redirect_uri = (
        redirect_uri
        or await in_thread(google_oauth_redirect_uri)
        or f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:4200')}/api/auth/google/callback/"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Exchange code for tokens
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": target_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            logger.error(
                "Google token exchange failed (status %s): %s",
                token_resp.status_code,
                token_resp.text,
            )
            raise ValueError(f"Token exchange failed: {token_resp.text}")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access_token returned by Google")

        # 2. Fetch user profile with access token
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if userinfo_resp.status_code != 200:
            logger.error(
                "Google userinfo fetch failed (status %s): %s",
                userinfo_resp.status_code,
                userinfo_resp.text,
            )
            raise ValueError(f"Userinfo fetch failed: {userinfo_resp.text}")

        user_info = userinfo_resp.json()
        return user_info


async def _generate_unique_username(base_name: str, email: str) -> str:
    """Generate a valid, unique username adhering to USERNAME_VALIDATOR regex."""
    # Preferred base: name if suitable, otherwise email username
    raw = base_name if (base_name and len(base_name) >= 3) else email.split("@")[0]
    # Replace non-alphanumeric chars (except . _ -) with underscore
    cleaned = re.sub(r"[^A-Za-z0-9._\-]", "_", raw).strip("._-")
    if len(cleaned) < 3:
        cleaned = f"user_{secrets.token_hex(3)}"
    cleaned = cleaned[:24]

    candidate = cleaned
    counter = 1
    while await User.objects.filter(username__iexact=candidate).aexists():
        candidate = f"{cleaned[:22]}_{counter}"
        counter += 1

    return candidate


def _apply_google_profile(user: User, full_name: str, avatar_url: str) -> list[str]:
    """Sync a Google profile onto an existing user without clobbering custom data.

    The Google display name replaces an empty name or a placeholder name that is
    just the username. The Google photo replaces an empty avatar or a previous
    Google-hosted avatar, while user-uploaded avatars are preserved.
    """
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
        not current_avatar or "googleusercontent.com" in current_avatar
    ):
        if current_avatar != incoming_avatar:
            user.avatar_url = incoming_avatar
            updates.append("avatar_url")

    return updates


def _create_oauth_user(
    *,
    email: str,
    username: str,
    full_name: str,
    avatar_url: str,
    google_id: str,
    role: str,
    is_active: bool,
    approval_status: str,
) -> User:
    """Synchronous helper to create and save an OAuth user with unusable password."""
    user = User(
        email=email.strip().lower(),
        username=username,
        full_name=full_name.strip()[:120],
        avatar_url=avatar_url,
        google_id=google_id,
        role=role,
        is_active=is_active,
        approval_status=approval_status,
    )
    user.set_unusable_password()
    user.save()
    return user


async def get_or_create_google_user(
    user_info: dict[str, Any], requested_role: str = ""
) -> tuple[User, bool, str | None]:
    """Find an existing user or create a new user from Google UserInfo.

    Returns:
        (user, created, error_detail)
        error_detail is None if the user is authorized to sign in immediately,
        or an error code ('select_role', 'approval_pending', 'registration_rejected', 'not_authorized').
    """
    from accounts.api import _notify_admins_of_owner_request
    from accounts.models import PlatformSettings

    google_id = str(user_info.get("sub") or "").strip()
    email = str(user_info.get("email") or "").strip().lower()
    full_name = str(user_info.get("name") or "").strip()
    avatar_url = str(user_info.get("picture") or "").strip()

    if not google_id or not email:
        raise ValueError("Google userinfo missing sub or email")

    # 1. Look up existing user by google_id
    user = await User.objects.filter(google_id=google_id).afirst()
    if user is not None:
        updates = _apply_google_profile(user, full_name, avatar_url)
        if updates:
            await user.asave(update_fields=updates)

    # 2. Look up existing user by email
    if user is None:
        user = await User.objects.filter(email__iexact=email).afirst()
        if user is not None:
            # Link Google account to this existing user and refresh its profile.
            user.google_id = google_id
            updates = ["google_id", *_apply_google_profile(user, full_name, avatar_url)]
            await user.asave(update_fields=updates)

    # 3. If user exists, inspect their approval and active status
    if user is not None:
        if user.approval_status == ApprovalStatus.PENDING:
            return user, False, "approval_pending"
        if user.approval_status == ApprovalStatus.REJECTED:
            return user, False, "registration_rejected"
        if not user.is_active:
            return user, False, "not_authorized"
        return user, False, None

    # 4. User does not exist, create new user
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

    username = await _generate_unique_username(full_name, email)

    user = await in_thread(
        _create_oauth_user,
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        google_id=google_id,
        role=role,
        is_active=is_active,
        approval_status=approval_status,
    )

    from accounts.account_notifications import notify_account_created

    await in_thread(notify_account_created, user, "Google")

    if needs_role:
        return user, True, "select_role"

    if approval_status == ApprovalStatus.PENDING:
        await in_thread(_notify_admins_of_owner_request, user)
        return user, True, "approval_pending"

    return user, True, None
