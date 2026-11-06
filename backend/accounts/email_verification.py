"""Email verification, real-email validation, and OTP delivery for RentEasy."""

from __future__ import annotations

import logging
import re
import secrets
import socket
from datetime import timedelta
from typing import Any

import httpx
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from accounts.models import EmailVerification
from core.bolt import in_thread

logger = logging.getLogger(__name__)

# RFC 5322 simplified email syntax
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

# Known disposable, temporary, and fake email domains
DISPOSABLE_DOMAINS: set[str] = {
    "mailinator.com",
    "10minutemail.com",
    "10minutemail.net",
    "10minutemail.org",
    "tempmail.com",
    "temp-mail.org",
    "temp-mail.io",
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamail.biz",
    "guerrillamail.info",
    "guerrillamail.de",
    "grr.la",
    "sharklasers.com",
    "trashmail.com",
    "trashmail.net",
    "trashmail.me",
    "yopmail.com",
    "yopmail.fr",
    "yopmail.net",
    "dispostable.com",
    "getairmail.com",
    "maildrop.cc",
    "throwawaymail.com",
    "fakemailgenerator.com",
    "mytemp.email",
    "generator.email",
    "emailondeck.com",
    "burnermail.io",
    "inboxkitten.com",
    "crazymailing.com",
    "mohmal.com",
    "mohmal.im",
    "inboxbear.com",
    "dropmail.me",
    "tempail.com",
    "spam4.me",
    "pokemail.net",
    "minutemailbox.com",
    "nada.ltd",
    "getnada.com",
    "abcfood.net",
    "disposablemail.com",
    "10mail.org",
    "fake.com",
    "test.com",
    "testing.com",
    "example.com",
    "example.org",
    "example.net",
    "mailnull.com",
    "kasmail.com",
    "spambox.us",
    "temporarymail.com",
    "armyspy.com",
    "cuvox.de",
    "dayrep.com",
    "einrot.com",
    "fleckens.hu",
    "gustr.com",
    "jourrapide.com",
    "rhyta.com",
    "superrito.com",
    "teleworm.us",
}

OTP_EXPIRY_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60


def is_valid_email_syntax(email: str) -> bool:
    """Check basic email formatting."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email))


async def is_real_email_domain(domain: str) -> bool:
    """Verify that a domain exists and is capable of receiving mail."""
    domain = domain.strip().lower()
    if not domain or "." not in domain:
        return False

    # 1. Reject known disposable domains
    if domain in DISPOSABLE_DOMAINS:
        return False

    # Check for subdomains of disposable domains
    parts = domain.split(".")
    if len(parts) > 2:
        root_domain = ".".join(parts[-2:])
        if root_domain in DISPOSABLE_DOMAINS:
            return False

    # Reject fake/reserved TLDs
    tld = parts[-1]
    if tld in {"invalid", "test", "example", "localhost", "local"}:
        return False

    # 2. Check MX records via Google DNS over HTTPS (DoH)
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(
                "https://dns.google/resolve",
                params={"name": domain, "type": "MX"},
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("Status")
                # Status 3 means NXDOMAIN (domain does not exist)
                if status == 3:
                    return False
                answers = data.get("Answer", [])
                # Has MX records
                if any(ans.get("type") == 15 for ans in answers):
                    return True

            # If no MX returned, check A record (fallback for direct SMTP host)
            resp_a = await client.get(
                "https://dns.google/resolve",
                params={"name": domain, "type": "A"},
            )
            if resp_a.status_code == 200:
                data_a = resp_a.json()
                if data_a.get("Status") == 3:
                    return False
                if any(ans.get("type") == 1 for ans in data_a.get("Answer", [])):
                    return True
    except Exception as exc:
        logger.debug(
            "DNS over HTTPS lookup failed for %s: %s; trying socket fallback",
            domain,
            exc,
        )

        # Fallback to local socket DNS lookup in worker thread
        def _socket_check():
            try:
                socket.getaddrinfo(domain, 25)
                return True
            except socket.gaierror:
                return False

        return await in_thread(_socket_check)

    return False


async def validate_real_email(email: str) -> tuple[bool, str | None]:
    """Validate that an email address is properly formatted, not disposable, and real.

    Returns:
        (is_valid, error_code)
        error_code: None, 'invalid_email_format', 'disposable_email_not_allowed', or 'email_domain_invalid'
    """
    clean_email = (email or "").strip().lower()
    if not is_valid_email_syntax(clean_email):
        return False, "invalid_email_format"

    domain = clean_email.split("@")[1]
    if domain in DISPOSABLE_DOMAINS:
        return False, "disposable_email_not_allowed"

    is_real = await is_real_email_domain(domain)
    if not is_real:
        return False, "email_domain_invalid"

    return True, None


def generate_otp_code() -> str:
    """Generate a secure 6-digit numeric OTP."""
    return f"{secrets.randbelow(900000) + 100000}"


def send_otp_email(email: str, code: str, purpose: str = "register") -> None:
    """Send verification OTP email to user."""
    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL", "RentEasy <noreply@renteasy.com>"
    )
    subject = f"RentEasy - Verification Code: {code}"

    text_content = (
        f"Welcome to RentEasy!\n\n"
        f"Your 6-digit email confirmation code is: {code}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you did not request this verification, please ignore this email.\n\n"
        f"— The RentEasy Team"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
        .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
        .brand {{ font-size: 22px; font-weight: 800; color: #2563eb; margin-bottom: 20px; }}
        .title {{ font-size: 18px; font-weight: 700; margin-bottom: 12px; }}
        .subtitle {{ font-size: 14px; color: #64748b; line-height: 1.5; margin-bottom: 24px; }}
        .otp-box {{ text-align: center; margin: 24px 0; background: #eff6ff; border: 1px dashed #bfdbfe; border-radius: 12px; padding: 18px; }}
        .otp-code {{ font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #1d4ed8; font-family: monospace; }}
        .footer {{ font-size: 12px; color: #94a3b8; text-align: center; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="brand">RentEasy</div>
        <div class="title">Verify Your Email Address</div>
        <div class="subtitle">Use the verification code below to complete your registration and activate your account:</div>
        <div class="otp-box">
          <div class="otp-code">{code}</div>
        </div>
        <div class="subtitle">This code is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong>. For your security, never share this code with anyone.</div>
        <div class="footer">RentEasy — Easy Rent, Happy Living.<br>If you did not request this email, you can safely ignore it.</div>
      </div>
    </body>
    </html>
    """

    logger.info(
        "========== [EMAIL OTP] Sending verification code %s to %s ==========",
        code,
        email,
    )
    send_mail(
        subject=subject,
        message=text_content,
        from_email=from_email,
        recipient_list=[email],
        html_message=html_content,
        fail_silently=False,
    )


async def create_and_send_verification_otp(
    email: str,
    payload: dict[str, Any],
    purpose: str = EmailVerification.Purpose.REGISTER,
) -> EmailVerification:
    """Store verification record and dispatch email to user."""
    clean_email = email.strip().lower()
    code = generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Invalidate existing pending OTPs for this email and purpose
    await EmailVerification.objects.filter(
        email=clean_email, purpose=purpose, is_verified=False
    ).aupdate(is_verified=True)

    verification = await EmailVerification.objects.acreate(
        email=clean_email,
        code=code,
        purpose=purpose,
        payload=payload,
        expires_at=expires_at,
    )

    await in_thread(send_otp_email, clean_email, code, purpose)
    return verification
