"""Record successful sign-ins for the superadmin session history.

Django's own session table tells us whether a session is still valid. This
module adds the human-readable context (device, browser, IP and approximate
location) without changing the authentication flow: tracking is best-effort
and never blocks a successful login.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from datetime import timedelta
from typing import Any

import httpx
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from accounts.models import AuditLog, LoginSession

logger = logging.getLogger(__name__)

_PRIVATE_IP = ipaddress.ip_address


def header_value(headers: Any, name: str) -> str:
    """Case-insensitive header lookup for Bolt/Django header mappings."""
    wanted = name.lower()
    for key, value in (headers or {}).items():
        if str(key).lower() == wanted:
            return str(value or "").strip()
    return ""


def extract_client_ip(headers: Any) -> str | None:
    """Return the public client address supplied by our trusted nginx proxy.

    nginx overwrites ``X-Real-IP`` and appends to ``X-Forwarded-For``. We
    prefer the former, then take the left-most forwarded address. Values that
    are not IP addresses (including spoofed junk) are ignored.
    """
    candidates = [
        header_value(headers, "cf-connecting-ip"),
        header_value(headers, "x-real-ip"),
        header_value(headers, "x-forwarded-for").split(",", 1)[0],
    ]
    for candidate in candidates:
        candidate = candidate.strip().strip('"')
        if not candidate or candidate.lower() == "unknown":
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def is_public_ip(value: str | None) -> bool:
    if not value:
        return False
    try:
        address = _PRIVATE_IP(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def parse_user_agent(user_agent: str) -> dict[str, str]:
    """Small, dependency-free UA summary suitable for a security table."""
    ua = (user_agent or "").strip()
    lower = ua.lower()

    if not ua:
        return {
            "device_type": LoginSession.DeviceType.UNKNOWN,
            "browser": "",
            "operating_system": "",
        }

    if re.search(r"bot|crawler|spider|slurp|preview|headless|curl|wget|python-requests|httpx", lower):
        device = LoginSession.DeviceType.BOT
    elif re.search(r"ipad|tablet|playbook|silk|kindle", lower) or (
        "android" in lower and "mobile" not in lower
    ):
        device = LoginSession.DeviceType.TABLET
    elif re.search(r"mobi|iphone|ipod|android|windows phone|blackberry", lower):
        device = LoginSession.DeviceType.MOBILE
    else:
        device = LoginSession.DeviceType.DESKTOP

    browsers = (
        ("Edg/", "Edge"),
        ("OPR/", "Opera"),
        ("SamsungBrowser/", "Samsung Internet"),
        ("Chrome/", "Chrome"),
        ("CriOS/", "Chrome"),
        ("Firefox/", "Firefox"),
        ("FxiOS/", "Firefox"),
        ("Safari/", "Safari"),
    )
    browser = next((label for token, label in browsers if token.lower() in lower), "")

    if "windows" in lower:
        operating_system = "Windows"
    elif "android" in lower:
        operating_system = "Android"
    elif "iphone" in lower or "ipad" in lower or "ipod" in lower:
        operating_system = "iOS"
    elif "mac os x" in lower or "macintosh" in lower:
        operating_system = "macOS"
    elif "cros" in lower:
        operating_system = "Chrome OS"
    elif "linux" in lower:
        operating_system = "Linux"
    else:
        operating_system = ""

    return {
        "device_type": device,
        "browser": browser[:40],
        "operating_system": operating_system[:40],
    }


def lookup_ip_location(ip: str | None) -> dict[str, str]:
    """Resolve a public IP to city/country using the free ipwho.is API.

    This is deliberately best-effort: a timeout, rate limit or provider
    outage must never prevent sign-in. Private/loopback addresses are skipped.
    """
    if not is_public_ip(ip):
        return {}
    try:
        with httpx.Client(timeout=2.5, follow_redirects=True) as client:
            response = client.get(f"https://ipwho.is/{ip}")
        if not response.is_success:
            return {}
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict) or not payload.get("success"):
        return {}
    return {
        "country_code": str(payload.get("country_code") or "")[:2].upper(),
        "country": str(payload.get("country") or "")[:80],
        "region": str(payload.get("region") or "")[:120],
        "city": str(payload.get("city") or "")[:120],
    }


def current_session_key(request: Any) -> str:
    session = getattr(request, "session", None)
    return str(getattr(session, "session_key", "") or "")


def record_login_session(
    user,
    request: Any,
    auth_method: str = "email",
) -> LoginSession | None:
    """Upsert the current Django session and append a login audit event."""
    try:
        session = getattr(request, "session", None)
        if session is None:
            return None
        if not session.session_key:
            session.save()
        session_key = str(session.session_key or "")
        if not session_key:
            return None

        headers = getattr(request, "headers", {}) or {}
        user_agent = header_value(headers, "user-agent")[:2000]
        ip_address = extract_client_ip(headers)
        device = parse_user_agent(user_agent)
        location = lookup_ip_location(ip_address)
        now = timezone.now()
        expires_at = (
            Session.objects.filter(session_key=session_key)
            .values_list("expire_date", flat=True)
            .first()
        ) or (now + timedelta(seconds=int(settings.SESSION_COOKIE_AGE)))

        login_session, _created = LoginSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                "user": user,
                "auth_method": str(auth_method or "email").lower()[:20],
                "ip_address": ip_address,
                "user_agent": user_agent,
                "device_type": device["device_type"],
                "browser": device["browser"],
                "operating_system": device["operating_system"],
                "country_code": location.get("country_code", ""),
                "country": location.get("country", ""),
                "region": location.get("region", ""),
                "city": location.get("city", ""),
                "last_seen_at": now,
                "session_expires_at": expires_at,
                "logged_out_at": None,
            },
        )

        place = ", ".join(
            part for part in (login_session.city, login_session.country) if part
        )
        summary = f"login via {auth_method}"
        if place:
            summary += f" from {place}"
        if ip_address:
            summary += f" ({ip_address})"
        AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGIN,
            entity="session",
            entity_id=str(user.pk),
            summary=summary[:255],
        )
        return login_session
    except Exception:  # pragma: no cover - security logging must not block login
        logger.exception("Could not record login session for user %s", getattr(user, "pk", None))
        return None


def end_login_session(request: Any) -> None:
    """Mark the current session as signed out before Django flushes it."""
    session_key = current_session_key(request)
    if not session_key:
        return
    LoginSession.objects.filter(
        session_key=session_key, logged_out_at__isnull=True
    ).update(logged_out_at=timezone.now())
