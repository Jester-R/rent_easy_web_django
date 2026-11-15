"""Resolve Google Maps share links to coordinates and reverse geocode for the Leaflet map."""

from __future__ import annotations

import html
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx

_COORDINATE_PATTERNS = (
    re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", re.I),
    re.compile(r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)"),
    re.compile(
        r"(?:[?&](?:q|query|ll|sll|center|latlng|daddr|markers)=)(-?\d+(?:\.\d+)?)(?:%2C|,\s*)(-?\d+(?:\.\d+)?)",
        re.I,
    ),
    re.compile(r"\[null,null,(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\]"),
)

_REVERSE_GEOCODE_CACHE: dict[str, dict] = {}


def _extract_url_candidate(value: str) -> str:
    """Extract an HTTP(S) URL from raw text, query string, or iframe markup."""
    text = value.strip()
    iframe_match = re.search(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', text, re.I)
    if iframe_match:
        return iframe_match.group(1).strip()
    url_match = re.search(r"https?://[^\s\"'<>]+", text)
    if url_match:
        return url_match.group(0).strip()
    return text


def _is_google_maps_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host in {
        "maps.app.goo.gl",
        "goo.gl",
        "google.com",
        "www.google.com",
        "maps.google.com",
    }:
        return True
    if host.endswith(".google.com") or host.endswith(".goo.gl"):
        return True
    # Support regional Google domains, e.g. google.com.kh, maps.google.com.kh, google.co.th
    return bool(re.match(r"^(?:[a-z0-9-]+\.)?google\.(?:com\.)?[a-z]{2,}$", host))


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

    # Check embed iframe format: !2d<lng>!3d<lat>
    embed_match = re.search(r"!2d(-?\d+(?:\.\d+)?)!3d(-?\d+(?:\.\d+)?)", text, re.I)
    if embed_match:
        lng, lat = float(embed_match.group(1)), float(embed_match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng):
            return lat, lng

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

    # Check standalone lat,lng pair
    pair_match = re.search(r"^\s*(-?\d{1,3}(?:\.\d+)?)[\s,;]+(-?\d{1,3}(?:\.\d+)?)\s*$", text)
    if pair_match:
        latitude, longitude = float(pair_match.group(1)), float(pair_match.group(2))
        if (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
            and (latitude or longitude)
        ):
            return latitude, longitude

    return None


async def resolve_google_maps_url(value: str) -> tuple[float, float] | None:
    """Follow a Google Maps share URL and extract its coordinates safely."""
    raw = (value or "").strip()
    if not raw or len(raw) > 4096:
        return None

    # First check if coordinates can be extracted directly without network requests
    direct = _extract_coordinates(raw)
    if direct:
        return direct

    url = _extract_url_candidate(raw)
    if not _is_allowed_maps_url(url):
        return None

    current_url = url
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for _ in range(8):
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


async def reverse_geocode_osm(latitude: float, longitude: float) -> dict:
    """Reverse geocode latitude/longitude using OpenStreetMap Nominatim."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return {"display_name": "", "address": {}}

    cache_key = f"{latitude:.5f},{longitude:.5f}"
    if cache_key in _REVERSE_GEOCODE_CACHE:
        return _REVERSE_GEOCODE_CACHE[cache_key]

    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "format": "jsonv2",
        "lat": str(latitude),
        "lon": str(longitude),
        "zoom": "18",
        "addressdetails": "1",
        "accept-language": "en,km",
    }
    headers = {
        "User-Agent": "RentEasyApp/1.0 (+https://renteasy.com)",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                result = {
                    "display_name": str(data.get("display_name") or ""),
                    "address": data.get("address") or {},
                }
                if len(_REVERSE_GEOCODE_CACHE) > 500:
                    _REVERSE_GEOCODE_CACHE.clear()
                _REVERSE_GEOCODE_CACHE[cache_key] = result
                return result
    except Exception:
        pass

    return {"display_name": "", "address": {}}
