from __future__ import annotations

import json

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from . import i18n


def site(request):
    return {
        "SITE_NAME": "Rent Easy",
        "SUPPORTED_LANGUAGES": [
            {"code": code, "label": meta["label"], "native_label": meta["native_label"], "flag": meta["flag"]}
            for code, meta in i18n.LANGUAGES.items()
        ],
        "DEFAULT_LANGUAGE": i18n.DEFAULT_LANGUAGE,
        "DEBUG": settings.DEBUG,
    }


def i18n_context(request):
    language = getattr(request, "LANGUAGE_CODE_UI", i18n.DEFAULT_LANGUAGE)
    # Only two languages ship, so the UI is a single toggle instead of a picker.
    other_code = next((code for code in i18n.LANGUAGES if code != language), i18n.DEFAULT_LANGUAGE)
    other = i18n.LANGUAGES[other_code]
    return {
        "LANG": language,
        "OTHER_LANGUAGE": {
            "code": other["code"],
            "label": other["label"],
            "native_label": other["native_label"],
        },
        "IS_KHMER": language == "km",
        "T": getattr(request, "translator", None) or i18n.Translator(language),
        "THEME": getattr(request, "theme", "light"),
        "IS_DARK": getattr(request, "theme", "light") == "dark",
    }


def js_config(request):
    """Boot payload consumed by ``static/js/app.js`` (jQuery layer)."""

    def url(name: str, fallback: str = "") -> str:
        try:
            return reverse(name)
        except NoReverseMatch:  # pragma: no cover - defensive
            return fallback

    language = getattr(request, "LANGUAGE_CODE_UI", i18n.DEFAULT_LANGUAGE)
    t = getattr(request, "translator", None) or i18n.Translator(language)

    string_keys = (
        "loading",
        "close",
        "no_results",
        "no_notifications",
        "no_notifications_body",
        "error_generic",
        "confirm",
        "cancel",
        "delete",
        "added_favorite",
        "copied",
        "booking_sent",
        "payment_recorded",
        "not_authorized",
        "active_booking_exists",
        "invalid_transition",
        "account_updated",
        "search_placeholder",
    )

    payload = {
        "lang": language,
        "catalog": {key: pair for key, pair in i18n.CATALOG.items()},
        "strings": {key: t(key) for key in string_keys},
        "urls": {
            "notificationsPreview": url("notifications:preview"),
            "notificationsBadge": url("notifications:badge"),
            "notificationsReadAll": url("notifications:read_all"),
            "health": url("health"),
        },
    }
    return {"RENTEASY_JS": json.dumps(payload, ensure_ascii=False)}
