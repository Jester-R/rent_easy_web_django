"""Optional email delivery for the application's in-app notifications."""

from __future__ import annotations

import logging
from html import escape

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification
from .rendering import notification_copy, render

logger = logging.getLogger(__name__)


def _email_address(recipient) -> str:
    email = (getattr(recipient, "email", "") or "").strip().lower()
    if not email or "@" not in email:
        return ""
    if not getattr(recipient, "is_email_verified", False):
        return ""
    domain = email.rsplit("@", 1)[-1]
    # Telegram-only accounts use a placeholder address that cannot receive mail.
    if domain == "telegram.local" or domain.endswith(".local"):
        return ""
    from accounts.email_verification import DISPOSABLE_DOMAINS

    if domain in DISPOSABLE_DOMAINS:
        return ""
    return email


def _notification_url(notification: Notification) -> str:
    base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:4200").rstrip("/")
    path = notification.get_absolute_url() or "/notifications/"
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}{path}"


def send_email_notification(notification_id: int) -> bool:
    """Mirror an in-app notification to the recipient's email address."""
    notification = (
        Notification.objects.filter(pk=notification_id)
        .select_related("recipient")
        .first()
    )
    if notification is None:
        return False

    recipient = notification.recipient
    email = _email_address(recipient)
    if not email:
        return False

    copy = notification_copy(notification)
    params = copy.get("params") or {}
    title_en = render(copy["title_en"], params)
    body_en = render(copy["body_en"], params)
    title_km = render(copy["title_km"], params) if copy["title_km"] else ""
    body_km = render(copy["body_km"], params) if copy["body_km"] else ""

    subject = f"RentEasy - {title_en}"[:150]
    url = _notification_url(notification)
    text_parts = [f"RentEasy\n\n{title_en}\n{body_en}"]
    if title_km or body_km:
        text_parts.append(f"\n{title_km}\n{body_km}")
    text_parts.append(f"\nView in RentEasy: {url}")
    text_content = "\n".join(text_parts)

    khmer_block = ""
    if title_km or body_km:
        khmer_block = (
            f'<div class="km"><div class="title">{escape(title_km)}</div>'
            f"<p>{escape(body_km)}</p></div>"
        )
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f8fafc;margin:0;padding:24px;color:#1e293b;">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;border:1px solid #e2e8f0;padding:28px;">
    <div style="font-size:20px;font-weight:800;color:#2563eb;margin-bottom:18px;">RentEasy</div>
    <div style="font-size:17px;font-weight:700;margin-bottom:8px;">{escape(title_en)}</div>
    <p style="font-size:14px;line-height:1.6;color:#475569;margin:0 0 18px;">{escape(body_en)}</p>
    {khmer_block}
    <p style="margin:22px 0 0;">
      <a href="{escape(url)}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:10px 18px;border-radius:10px;">Open RentEasy</a>
    </p>
    <div style="font-size:12px;color:#94a3b8;text-align:center;margin-top:24px;border-top:1px solid #f1f5f9;padding-top:14px;">RentEasy — Easy Rent, Happy Living.</div>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=getattr(
                settings, "DEFAULT_FROM_EMAIL", "RentEasy <noreply@renteasy.com>"
            ),
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        # Email delivery is best-effort and must not break the in-app feed.
        logger.warning(
            "Email notification delivery failed (%s)", type(exc).__name__
        )
        return False
