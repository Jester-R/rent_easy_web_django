from __future__ import annotations

from django.conf import settings
from django.utils import translation as django_translation

from . import i18n


class LanguageMiddleware:
    """Resolves the active UI language from cookie -> session -> default."""

    LANGUAGE_COOKIE = "renteasy_lang"
    SESSION_KEY = "renteasy_language"
    SUPPORTED = set(i18n.SUPPORTED_LANGUAGE_CODES)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = self._resolve(request)
        django_translation.activate(language)
        request.LANGUAGE_CODE_UI = language
        request.translator = i18n.Translator(language)
        response = self.get_response(request)
        return response

    def _resolve(self, request) -> str:
        cookie = request.COOKIES.get(self.LANGUAGE_COOKIE, "")
        if cookie in self.SUPPORTED:
            return cookie

        session_lang = request.session.get(self.SESSION_KEY, "")
        if session_lang in self.SUPPORTED:
            return session_lang

        accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "").lower()
        if accept:
            best, best_index = None, None
            for index, chunk in enumerate(accept.split(",")):
                code = chunk.split(";")[0].strip()[:2]
                if code in self.SUPPORTED:
                    if best_index is None or index < best_index:
                        best, best_index = code, index
            if best:
                return best

        return i18n.DEFAULT_LANGUAGE


def persist_language(request, language: str, response):
    """Attach a language cookie to ``response`` and remember it in the session."""
    if language in set(i18n.SUPPORTED_LANGUAGE_CODES):
        request.session[LanguageMiddleware.SESSION_KEY] = language
        response.set_cookie(
            LanguageMiddleware.LANGUAGE_COOKIE,
            language,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
        )
    return response


DEFAULT_THEME = "light"
THEMES = {DEFAULT_THEME, "dark"}
THEME_COOKIE = "renteasy_theme"
THEME_SESSION_KEY = "renteasy_theme"


class ThemeMiddleware:
    """Resolves light/dark appearance from cookie -> session -> default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie = request.COOKIES.get(THEME_COOKIE, "")
        session_theme = request.session.get(THEME_SESSION_KEY, "")
        theme = (
            cookie
            if cookie in THEMES
            else session_theme
            if session_theme in THEMES
            else DEFAULT_THEME
        )
        request.theme = theme
        response = self.get_response(request)
        response.setdefault("X-RentEasy-Theme", theme)
        return response


def persist_theme(request, theme: str, response):
    if theme in THEMES:
        request.session[THEME_SESSION_KEY] = theme
        response.set_cookie(
            THEME_COOKIE, theme, max_age=60 * 60 * 24 * 365, samesite="Lax"
        )
    return response


FLASH_SESSION_KEY = "renteasy_flash"

#: session flash key -> (translation key, message level)
FLASH_MAP: dict[str, tuple[str, str]] = {
    "registration_complete": ("registration_complete", "success"),
    "account_created": ("account_created", "success"),
    "account_updated": ("account_updated", "success"),
    "booking_sent": ("booking_sent", "success"),
    "booking_approved": ("status_approved", "success"),
    "booking_rejected": ("status_rejected", "info"),
    "booking_cancelled": ("status_cancelled", "info"),
    "booking_created": ("bookings", "success"),
    "booking_updated": ("bookings", "success"),
    "payment_recorded": ("payment_recorded", "success"),
    "payment_failed": ("payment_failed", "error"),
    "payment_created": ("payments", "success"),
    "payment_updated": ("payments", "success"),
    "refund_processed": ("notif_refund_processed", "success"),
    "refund_created": ("refunds", "success"),
    "property_created": ("properties", "success"),
    "property_updated": ("properties", "success"),
    "property_deleted": ("properties", "info"),
    "record_deleted": ("delete", "success"),
    "records_deleted": ("delete", "success"),
    "active_booking_exists": ("active_booking_exists", "error"),
    "invalid_transition": ("invalid_transition", "error"),
    "not_authorized": ("not_authorized", "error"),
    "move_in_past": ("move_in_past", "error"),
    "credentials_invalid": ("invalid_credentials", "error"),
    "password_too_short": ("password_too_short", "error"),
}


class FlashMiddleware:
    """Turns the compact ``session['renteasy_flash']`` key into a translated toast."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib import messages

        key = request.session.pop(FLASH_SESSION_KEY, None)
        if key:
            entry = FLASH_MAP.get(key)
            if entry:
                translator = getattr(request, "translator", None) or i18n.Translator(
                    getattr(request, "LANGUAGE_CODE_UI", "en")
                )
                text, level = entry
                level = {
                    "success": messages.SUCCESS,
                    "error": messages.ERROR,
                    "info": messages.INFO,
                }.get(level, messages.INFO)
                messages.add_message(request, level, translator(text), extra_tags=key)
        return self.get_response(request)


__all__ = [
    "LanguageMiddleware",
    "ThemeMiddleware",
    "FlashMiddleware",
    "FLASH_MAP",
    "FLASH_SESSION_KEY",
    "persist_language",
    "persist_theme",
    "THEMES",
    "THEME_COOKIE",
    "LANGUAGE_COOKIE",
    "settings",
]
