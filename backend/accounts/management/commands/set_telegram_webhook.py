"""Register the Telegram bot webhook used by bot deep-link sign-in."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import httpx


class Command(BaseCommand):
    help = "Set (or inspect/delete) the Telegram bot webhook for RentEasy login."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="",
            help="Public webhook URL. Defaults to TELEGRAM_WEBHOOK_URL or FRONTEND_BASE_URL/api/telegram/webhook/.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete the current webhook instead of setting one.",
        )
        parser.add_argument(
            "--info",
            action="store_true",
            help="Print the current webhook information.",
        )

    def handle(self, *args, **options):
        # Never print request URLs at INFO: they contain the bot token.
        logging.getLogger("httpx").setLevel(logging.WARNING)

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured")

        api_base = f"https://api.telegram.org/bot{token}"

        if options["info"]:
            self._print(httpx.get(f"{api_base}/getWebhookInfo", timeout=10.0))
            return

        if options["delete"]:
            self._print(httpx.post(f"{api_base}/deleteWebhook", timeout=10.0))
            return

        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "").strip()
        if not secret:
            raise CommandError(
                "TELEGRAM_WEBHOOK_SECRET is not configured. Generate one with "
                '`python -c "import secrets; print(secrets.token_hex(32))"` '
                "and add it to .env."
            )

        url = options["url"].strip()
        if not url:
            url = (
                getattr(settings, "TELEGRAM_WEBHOOK_URL", "").strip()
                or f"{settings.FRONTEND_BASE_URL.rstrip('/')}/api/telegram/webhook/"
            )

        response = httpx.post(
            f"{api_base}/setWebhook",
            data={
                "url": url,
                "secret_token": secret,
                "allowed_updates": '["message"]',
            },
            timeout=15.0,
        )
        self._print(response)
        if response.is_success:
            self.stdout.write(self.style.SUCCESS(f"Webhook set to {url}"))

    def _print(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        self.stdout.write(f"HTTP {response.status_code}: {payload}")
