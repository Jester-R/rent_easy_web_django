from __future__ import annotations

from django import template
from django.utils import translation as django_translation
from django.utils.safestring import mark_safe

from core import icons as icon_lib
from core.i18n import DEFAULT_LANGUAGE as i18n_DEFAULT_LANGUAGE
from core.i18n import REFUND_REASON_KEYS, Translator

register = template.Library()


@register.simple_tag(name="icon")
def icon_tag(name: str, size: int = 20, css_class: str = "", stroke_width=None) -> str:
    """Render an inline SVG icon."""
    return mark_safe(icon_lib.render_icon(name, size=size, class_name=css_class, stroke_width=stroke_width))


@register.filter(name="usd")
def usd(value, decimals: int = 0) -> str:
    """Format a number as ``$1,234`` — mirrors the app's ``CurrencyExtension.toUsd``."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "$0"
    if decimals == 0:
        rounded = int(round(number))
        return "${:,}".format(rounded)
    return "${:,.{}f}".format(number, decimals)


@register.filter(name="pretty_date")
def pretty_date(value) -> str:
    """``dd MMM yyyy, hh:mm AM/PM`` — mirrors ``AppDateUtils.pretty``."""
    if not value:
        return ""
    try:
        if value.hour and (value.hour >= 12):
            suffix = "PM"
            hour = value.hour if value.hour <= 12 else value.hour - 12
        else:
            suffix = "AM"
            hour = value.hour if 1 <= value.hour <= 12 else (value.hour or 12)
        hour = 12 if hour == 0 else hour
        return "{} {}, {}:{:02d} {}".format(
            value.day, value.strftime("%b"), value.year, hour, value.minute, suffix
        )
    except (AttributeError, ValueError):
        return str(value)


@register.filter(name="short_date")
def short_date(value) -> str:
    """``dd/MM/yyyy`` — mirrors the app's date-picker subtitle format."""
    if not value:
        return ""
    try:
        return "{:02d}/{:02d}/{:04d}".format(value.day, value.month, value.year)
    except (AttributeError, ValueError):
        return str(value)


@register.filter(name="iso_date")
def iso_date(value) -> str:
    if not value:
        return ""
    try:
        return "{:04d}-{:02d}-{:02d}".format(value.year, value.month, value.day)
    except (AttributeError, ValueError):
        return ""


@register.filter(name="booking_pill")
def booking_pill(booking) -> str:
    t = Translator(getattr(booking, "_lang", "en"))
    return t.status_pill(getattr(booking, "status", ""))[1]


def _translator(context) -> Translator:
    t = context.get("T")
    return t if isinstance(t, Translator) else Translator("en")


def _active_language() -> str:
    return django_translation.get_language() or i18n_DEFAULT_LANGUAGE


@register.simple_tag(takes_context=True)
def booking_status(context, booking):
    """``{% booking_status booking as st %}`` -> ``st.label`` / ``st.css``."""
    label, css = _translator(context).status_pill(getattr(booking, "status", ""))
    return {"label": label, "css": css, "raw": getattr(booking, "status", "")}


@register.simple_tag(takes_context=True)
def payment_status(context, payment):
    """``{% payment_status payment as ps %}`` -> ``ps.label`` / ``ps.css``."""
    label, css = _translator(context).payment_pill(payment)
    return {"label": label, "css": css, "raw": getattr(payment, "status", "")}


@register.simple_tag(takes_context=True)
def refund_status(context, payment):
    """``{% refund_status payment as rs %}`` -> ``rs.label`` / ``rs.css``."""
    t = _translator(context)
    raw = getattr(payment, "refund_status", "None")
    css = {"Processed": "pill-refunded", "Pending": "pill-pending"}.get(raw, "pill-neutral")
    return {"label": t.refund_status(raw), "css": css, "raw": raw}


@register.simple_tag(takes_context=True)
def status_label(context, raw, domain: str = "booking"):
    """``{% status_label "Pending" as st %}`` -> label/pill class for a raw status."""
    t = _translator(context)
    if domain == "payment":
        css = {"Success": "pill-approved", "Failed": "pill-rejected"}.get(raw, "pill-neutral")
        return {"label": t.payment_status(raw), "css": css, "raw": raw}
    if domain == "refund":
        css = {"Processed": "pill-refunded", "Pending": "pill-pending"}.get(raw, "pill-neutral")
        return {"label": t.refund_status(raw), "css": css, "raw": raw}
    label, css = t.status_pill(raw)
    return {"label": label, "css": css, "raw": raw}


METHOD_ICONS = {"ABA Pay (Mock)": "layers", "Wing (Mock)": "send", "Credit Card (Mock)": "card"}


@register.simple_tag(takes_context=True)
def method_label(context, raw):
    """``{% method_label payment.method as m %}`` -> translated label + icon."""
    t = _translator(context)
    return {"label": t.method_label(raw), "icon": METHOD_ICONS.get(raw, "card"), "raw": raw}


@register.simple_tag(takes_context=True)
def refund_option(context, raw):
    """Translated label for a refund-status filter option."""
    return {"label": _translator(context).refund_option(raw), "raw": raw}


@register.simple_tag(takes_context=True)
def role_label(context, role):
    return {"label": _translator(context).role_label(role), "raw": role or ""}


@register.simple_tag(takes_context=True)
def notif(context, item):
    """``{% notif item as n %}`` -> translated ``n.title`` / ``n.body``."""
    t = _translator(context)
    params = getattr(item, "params", None) or {}
    return {
        "title": t(getattr(item, "title_key", ""), **params),
        "body": t(getattr(item, "body_key", ""), **params),
        "href": getattr(item, "link", "") or "",
        "read": getattr(item, "is_read", True),
    }


@register.simple_tag(takes_context=True)
def party(context, booking, audience: str):
    """``{% party booking audience as p %}`` -> the counterparty user + role label."""
    t = _translator(context)
    other = getattr(booking, "owner", None) if audience == "renter" else getattr(booking, "renter", None)
    return {
        "user": other,
        "role_key": "property_owner" if audience == "renter" else "renter",
        "role": t.role_label(other.role if other else None),
    }


@register.simple_tag(takes_context=True)
def refund_reason(context, raw: str) -> str:
    """``{% refund_reason "other" %}`` -> translated refund reason."""
    return _translator(context)(REFUND_REASON_KEYS.get(raw, "reason_other"))


@register.simple_tag(takes_context=True, name="nav_active")
def nav_active(context, *names: str, prefix: bool = False) -> str:
    """``{% nav_active 'console:users' prefix=True %}`` -> ``is-active`` on match.

    Works from inside an ``{% include %}`` (where child ``{% block %}`` overrides
    cannot reach), by comparing the resolved view name.
    """
    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    if match is None or not names:
        return ""
    current_ns = (match.namespace or "").split(":")[0]
    current_name = match.url_name or ""
    for candidate in names:
        wanted_ns, _, wanted_name = candidate.partition(":")
        wanted_ns = wanted_ns or current_ns
        if wanted_ns != current_ns:
            continue
        if current_name == wanted_name or (prefix and current_name.startswith(wanted_name)):
            return "is-active"
    return ""


@register.simple_tag(takes_context=True, name="t")
def translate_tag(context, key: str, **kwargs) -> str:
    """``{% t 'key' %}`` / ``{% t 'key' count=n %}``.

    A kwarg value written as ``@other_key`` is translated first, which lets
    messages compose catalog entries, e.g. ``{% t 'field_required' field=@title %}``.
    """
    t = _translator(context)
    resolved = {
        name: (t(value[1:]) if isinstance(value, str) and value.startswith("@") else value)
        for name, value in kwargs.items()
    }
    return t(key, **resolved)


@register.filter(name="t")
def translate_filter(key, **kwargs) -> str:
    """``{{ 'key'|t }}`` — resolve a catalog key for the active language."""
    if not isinstance(key, str):
        return ""
    return Translator(_active_language())(key, **kwargs)


@register.filter(name="initials")
def initials(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "?"
    parts = [p for p in text.replace(".", " ").split() if p]
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@register.filter(name="split_list")
def split_list(value):
    return [item for item in (value or "").split(",") if item.strip()]


@register.filter(name="get_item")
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter(name="add_class")
def add_class(value, extra: str) -> str:
    base = value if isinstance(value, str) else ""
    classes = [c for c in base.split() if c]
    for c in (extra or "").split():
        if c and c not in classes:
            classes.append(c)
    return " ".join(classes)


@register.filter(name="multiply")
def multiply(value, factor):
    try:
        return float(value or 0) * float(factor)
    except (TypeError, ValueError):
        return 0
