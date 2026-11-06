"""Resolve Google Maps share links to coordinates for the Leaflet map."""

from __future__ import annotations

import html
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx

_COORDINATE_PATTERNS = (
    re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", re.I),
    re.compile(r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)"),
    re.compile(
        r"(?:[?&](?:q|query|ll|sll|center|latlng|daddr)=)(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        re.I,
    ),
)


def _is_google_maps_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host in {
        "maps.app.goo.gl",
        "goo.gl",
        "google.com",
        "www.google.com",
        "maps.google.com",
    }


def _is_allowed_maps_url(value: str) -> bool:
    parsed = urlparse(value)
    try:
        allowed_port = parsed.port in {None, 80, 443}
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and _is_google_maps_host(parsed.hostname)
        and allowed_port
    )


def _extract_coordinates(value: str) -> tuple[float, float] | None:
    text = value
    for _ in range(2):
        text = html.unescape(unquote(text))
    for pattern in _COORDINATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        latitude, longitude = float(match.group(1)), float(match.group(2))
        if (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
            and (latitude or longitude)
        ):
            return latitude, longitude
    return None


async def resolve_google_maps_url(value: str) -> tuple[float, float] | None:
    """Follow a Google Maps share URL and extract its coordinates safely."""
    value = value.strip()
    if not value or len(value) > 2048:
        return None

    if not _is_allowed_maps_url(value):
        return None

    current_url = value
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for _ in range(6):
            coordinates = _extract_coordinates(current_url)
            if coordinates:
                return coordinates

            response = await client.get(
                current_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,km;q=0.8",
                },
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                destination = response.headers.get("location")
                if not destination:
                    return None
                current_url = urljoin(current_url, destination)
                if not _is_allowed_maps_url(current_url):
                    return None
                continue
            if response.status_code >= 400:
                return None
            return _extract_coordinates(str(response.url)) or _extract_coordinates(
                response.text
            )
    return None
