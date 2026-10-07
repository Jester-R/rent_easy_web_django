"""
Inline SVG icon set for RentEasy Web.

A single stroke-based (Feather-like) 24x24 grid keeps the icon language
consistent across the web UI and avoids shipping an icon webfont.
"""

from __future__ import annotations

_STROKE_ATTRS = (
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
)

# name -> inner SVG markup (no <svg> wrapper)
ICONS: dict[str, str] = {
    # ---- navigation / structure -------------------------------------
    "logo": (
        '<path d="M3 11.2 12 4l9 7.2"/>'
        '<path d="M5.5 10v10h13V10"/>'
        '<path d="M9.5 20v-5.5h5V20"/>'
    ),
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.6V21h13V9.6"/><path d="M9.75 21v-5.5h4.5V21"/>',
    "dashboard": '<rect x="3" y="3" width="7.5" height="8.5" rx="1.5"/><rect x="13.5" y="3" width="7.5" height="5.5" rx="1.5"/><rect x="13.5" y="11.5" width="7.5" height="9.5" rx="1.5"/><rect x="3" y="14.5" width="7.5" height="6.5" rx="1.5"/>',
    "grid": '<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "building": '<path d="M3 21h18"/><path d="M5 21V5.5A1.5 1.5 0 0 1 6.5 4h7A1.5 1.5 0 0 1 15 5.5V21"/><path d="M15 10h3.5A1.5 1.5 0 0 1 20 11.5V21"/><path d="M8 8h4M8 12h4M8 16h4M17.5 14h.01M17.5 17.5h.01"/>',
    "store": '<path d="M3.5 9.5 5 4h14l1.5 5.5"/><path d="M3.5 9.5a2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0"/><path d="M5 11.5V20h14v-8.5"/><path d="M9.5 20v-4.5h5V20"/>',
    "inbox": '<path d="M3 13h4.5l1.5 3h6l1.5-3H21"/><path d="M5.4 4.8 3 13v5.5A1.5 1.5 0 0 0 4.5 20h15a1.5 1.5 0 0 0 1.5-1.5V13l-2.4-8.2A1.5 1.5 0 0 0 17.2 4H6.8a1.5 1.5 0 0 0-1.4.8Z"/>',
    "layers": '<path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z"/><path d="m3 12.5 9 4.5 9-4.5"/><path d="m3 17 9 4.5 9-4.5"/>',
    # ---- people / auth ----------------------------------------------
    "user": '<path d="M12 12.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
    "users": '<path d="M9.5 12a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5Z"/><path d="M2.5 20.5a7 7 0 0 1 14 0"/><path d="M16.5 5.2a3.75 3.75 0 0 1 0 7.1"/><path d="M18 14.2a7 7 0 0 1 3.5 6.3"/>',
    "user-plus": '<path d="M14.5 12a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z"/><path d="M3 20.5a7.5 7.5 0 0 1 11.5-6.4"/><path d="M18.5 15.5v6M15.5 18.5h6"/>',
    "user-check": '<path d="M14.5 12a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z"/><path d="M3 20.5a7.5 7.5 0 0 1 11.5-6.4"/><path d="m15.5 17.5 2 2 4-4"/>',
    "user-search": '<circle cx="10" cy="8" r="3.75"/><path d="M3 20.5a7 7 0 0 1 10.9-5.8"/><circle cx="17" cy="16" r="3"/><path d="m19.4 18.4 2.1 2.1"/>',
    "shield": '<path d="M12 3 5 5.5v5.8c0 4.3 2.9 7.7 7 9.7 4.1-2 7-5.4 7-9.7V5.5L12 3Z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
    "shield-admin": '<path d="M12 3 5 5.5v5.8c0 4.3 2.9 7.7 7 9.7 4.1-2 7-5.4 7-9.7V5.5L12 3Z"/><circle cx="12" cy="11" r="1.8"/><path d="M8.8 16.4a3.6 3.6 0 0 1 6.4 0"/>',
    "lock": '<rect x="4.5" y="10" width="15" height="10.5" rx="2"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.6 6.6 8.4 6 8.4-6"/>',
    "logout": '<path d="M15 8V5.5A1.5 1.5 0 0 0 13.5 4h-8A1.5 1.5 0 0 0 4 5.5v13A1.5 1.5 0 0 0 5.5 20h8a1.5 1.5 0 0 0 1.5-1.5V16"/><path d="M10 12h11"/><path d="m17.5 8.5 3.5 3.5-3.5 3.5"/>',
    "login": '<path d="M9 8V5.5A1.5 1.5 0 0 1 10.5 4h8A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 9 18.5V16"/><path d="M14 12H3"/><path d="m6.5 8.5-3.5 3.5 3.5 3.5"/>',
    # ---- actions ----------------------------------------------------
    "search": '<circle cx="10.75" cy="10.75" r="6.25"/><path d="m15.5 15.5 4.5 4.5"/>',
    "filter": '<path d="M3.5 5.5h17l-6.6 7.6V19l-3.8-2.2v-3.7L3.5 5.5Z"/>',
    "sliders": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.1"/><circle cx="9" cy="17" r="2.1"/>',
    "sort": '<path d="M7 4v16"/><path d="m3.5 7 3.5-3 3.5 3"/><path d="M17 20V4"/><path d="m13.5 17 3.5 3 3.5-3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "x": '<path d="m6 6 12 12M18 6 6 18"/>',
    "check": '<path d="m4.5 12.5 5 5 10-11"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.7 2.7L16 9.5"/>',
    "x-circle": '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    "alert": '<path d="M10.7 3.9 2.6 17.5A1.5 1.5 0 0 0 3.9 19.8h16.2a1.5 1.5 0 0 0 1.3-2.3L13.3 3.9a1.5 1.5 0 0 0-2.6 0Z"/><path d="M12 9v4.2M12 16.4h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8h.01"/>',
    "trash": '<path d="M4 6.5h16"/><path d="M9 6.5V4.8A1.3 1.3 0 0 1 10.3 3.5h3.4A1.3 1.3 0 0 1 15 4.8v1.7"/><path d="M6.5 6.5 7.4 19a1.5 1.5 0 0 0 1.5 1.4h6.2a1.5 1.5 0 0 0 1.5-1.4l.9-12.5"/><path d="M10.5 10v6.5M13.5 10v6.5"/>',
    "edit": '<path d="M4 20h4.2L19 9.2a2 2 0 0 0 0-2.8l-1.4-1.4a2 2 0 0 0-2.8 0L4 15.8V20Z"/><path d="m14.5 6.5 3 3"/>',
    "external": '<path d="M13.5 4H20v6.5"/><path d="M20 4 11 13"/><path d="M19 14v5.5a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 19.5v-12A1.5 1.5 0 0 1 5.5 6H11"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20.5 4v4.5H16"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
    # ---- chevrons / arrows ------------------------------------------
    "chevron-down": '<path d="m6 9.5 6 6 6-6"/>',
    "chevron-up": '<path d="m6 14.5 6-6 6 6"/>',
    "chevron-right": '<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
    "chevron-left": '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
    "arrow-left": '<path d="M20 12H4"/><path d="m10 6-6 6 6 6"/>',
    "arrow-right": '<path d="M4 12h16"/><path d="m14 6 6 6-6 6"/>',
    "arrow-up-right": '<path d="M7 17 17 7"/><path d="M9 7h8v8"/>',
    # ---- money / payments -------------------------------------------
    "card": '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M2.5 9.5h19"/><path d="M6.5 15h3.5"/>',
    "receipt": '<path d="M5 3.5h14v17l-2.3-1.6-2.35 1.6-2.35-1.6-2.35 1.6L7.3 18.9 5 20.5v-17Z"/><path d="M8.5 8.5h7M8.5 12.5h7"/>',
    "wallet": '<path d="M3.5 7.5A2 2 0 0 1 5.5 5.5H18a2 2 0 0 1 2 2v1"/><rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M20.5 12.5H16a2 2 0 0 0 0 4h4.5"/>',
    "dollar": '<path d="M12 3.5v17"/><path d="M16 7.5A3 3 0 0 0 13.5 5.5H10a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6h-3.5A3 3 0 0 1 8 15.5"/>',
    "trending-up": '<path d="m3.5 16.5 5.5-5.5 3.5 3.5 6-6.5"/><path d="M15 8h4.5v4.5"/>',
    "refund": '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20.5 4v4.5H16"/><path d="M12 8.5v7M9.5 10h4a1.75 1.75 0 0 1 0 3.5h-4"/>',
    # ---- property -----------------------------------------------------
    "map-pin": '<path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11Z"/><circle cx="12" cy="10" r="2.75"/>',
    "bed": '<path d="M3 18V7"/><path d="M3 12h18v6"/><path d="M21 18v-4.5A1.5 1.5 0 0 0 19.5 12H15v-2a2 2 0 0 0-2-2H9.5A1.5 1.5 0 0 0 8 9.5V12"/><circle cx="6" cy="10" r="1.6"/>',
    "bath": '<path d="M3 12.5h18"/><path d="M4.5 12.5V6A2 2 0 0 1 6.5 4h.5a1.5 1.5 0 0 1 1.5 1.5V8"/><path d="M4.5 12.5V16a4 4 0 0 0 4 4h7a4 4 0 0 0 4-4v-3.5"/><path d="M7 20.5 5.5 22M17 20.5 18.5 22"/>',
    "wifi": '<path d="M2.5 9a14 14 0 0 1 19 0"/><path d="M6 12.6a9 9 0 0 1 12 0"/><path d="M9.4 16.2a4.4 4.4 0 0 1 5.2 0"/><path d="M12 19.5h.01"/>',
    "city": '<path d="M3 21h18"/><path d="M5 21V8.5A1.5 1.5 0 0 1 6.5 7h3A1.5 1.5 0 0 1 11 8.5V21"/><path d="M11 12.5h6.5A1.5 1.5 0 0 1 19 14v7"/><path d="M7.5 10.5h1M7.5 14h1M7.5 17.5h1M15 16h.01M15 18.5h.01"/>',
    "key": '<circle cx="8" cy="12" r="4"/><path d="M12 12h9"/><path d="M17.5 12v3.5M20.5 12v2.5"/>',
    "door": '<path d="M5 21V4.5A1.5 1.5 0 0 1 6.5 3H16l3 3.5V21"/><path d="M3.5 21h17"/><circle cx="13" cy="12.5" r="1"/>',
    "document": '<path d="M6 3.5h7l5 5V20a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 5 20V5a1.5 1.5 0 0 1 1-1.5Z" transform="translate(1 0)"/><path d="M13 3.5V9h5"/><path d="M9 13h6M9 16.5h6"/>',
    # ---- booking ------------------------------------------------------
    "clipboard": '<path d="M9 4.5H7.5A1.5 1.5 0 0 0 6 6v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 20V6a1.5 1.5 0 0 0-1.5-1.5H15"/><rect x="9" y="2.5" width="6" height="4" rx="1.2"/><path d="M9 11h6M9 14.5h4"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M3.5 9.5h17"/><path d="M8 3v4M16 3v4"/><path d="M8 13.5h.01M12 13.5h.01M16 13.5h.01M8 17h.01M12 17h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l3.4 2"/>',
    "rotate-ccw": '<path d="M3 5v6h6"/><path d="M3.5 11a8.5 8.5 0 1 1 .9 5.4"/>',
    "note": '<path d="M20 4H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1Z"/><path d="M7 9h10M7 12.5h10M7 16h6"/>',
    # ---- misc ---------------------------------------------------------
    "bell": '<path d="M18 15.5V10a6 6 0 1 0-12 0v5.5L4 18h16l-2-2.5Z"/><path d="M9.5 21h5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3.2 9.5h17.6M3.2 14.5h17.6"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
    "sun": '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6"/>',
    "moon": '<path d="M20 14.2A8.4 8.4 0 0 1 9.8 4 8.5 8.5 0 1 0 20 14.2Z"/>',
    "monitor": '<rect x="2.5" y="4" width="19" height="13" rx="2"/><path d="M8.5 21h7M12 17v4"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "sparkle": '<path d="M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.5 10.1 12.8 4.5 10.9 10.1 9 12 3.5Z"/><path d="M18.5 16.5 19.3 19l2.5.8-2.5.8-.8 2.5-.8-2.5-2.5-.8 2.5-.8.8-2.5Z"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "sparkles-badge": '<path d="M12 2.8 14 8l5.2 2-5.2 2-2 5.2-2-5.2L4.8 10 10 8l2-5.2Z"/><circle cx="18.5" cy="17.5" r="3"/>',
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    "chart": '<path d="M3.5 20.5h17"/><path d="M6.5 17V11M11 17V6.5M15.5 17v-4M20 17V8"/>',
    "copy": '<rect x="8" y="8" width="12.5" height="12.5" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4H5.5A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
    "heart": '<path d="M12 20.4S3.6 15.1 3.6 9.4A4.85 4.85 0 0 1 12 6.3a4.85 4.85 0 0 1 8.4 3.1c0 5.7-8.4 11-8.4 11Z"/>',
    "heart-filled": '<path d="M12 20.4S3.6 15.1 3.6 9.4A4.85 4.85 0 0 1 12 6.3a4.85 4.85 0 0 1 8.4 3.1c0 5.7-8.4 11-8.4 11Z" fill="currentColor"/>',
    "download": '<path d="M12 3.5v11"/><path d="m7.5 10 4.5 4.5 4.5-4.5"/><path d="M4 19.5h16"/>',
    "send": '<path d="M21 3 10.5 13.5"/><path d="M21 3 14.4 21l-3.9-7.5L3 9.6 21 3Z"/>',
    "star": '<path d="m12 3.5 2.6 5.6 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.9l6-.8L12 3.5Z"/>',
    "eye-off": '<path d="M4 4.5 20 20.5"/><path d="M9.6 6.3A9.5 9.5 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.4 3.1"/><path d="M6.6 8.1A16.8 16.8 0 0 0 2.5 12S6 18 12 18a9.4 9.4 0 0 0 3.4-.6"/><path d="M9.9 10a3 3 0 0 0 4.1 4.2"/>',
    "package": '<path d="M20.5 7.6v8.8a1.5 1.5 0 0 1-.8 1.3l-7 3.6a1.5 1.5 0 0 1-1.4 0l-7-3.6a1.5 1.5 0 0 1-.8-1.3V7.6a1.5 1.5 0 0 1 .8-1.3l7-3.6a1.5 1.5 0 0 1 1.4 0l7 3.6a1.5 1.5 0 0 1 .8 1.3Z"/><path d="m3.8 7 8.2 4.2L20.2 7"/><path d="M12 21V11.2"/>',
}


def render_icon(
    name: str,
    size: int | str = 20,
    class_name: str = "",
    stroke_width: float | str | None = None,
) -> str:
    """Return inline SVG markup for ``name``."""
    body = ICONS.get(name)
    if body is None:
        body = ICONS["info"]
    attrs = _STROKE_ATTRS
    if stroke_width is not None:
        attrs = attrs.replace('stroke-width="1.75"', f'stroke-width="{stroke_width}"')
    cls = f' class="{class_name}"' if class_name else ""
    return f'<svg {attrs}{cls} width="{size}" height="{size}">{body}</svg>'
