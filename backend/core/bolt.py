"""Shared helpers for the Django-Bolt JSON API.

The API is served by ``runbolt`` (Rust HTTP server).  Handlers are ``async
def`` coroutines that receive the Bolt ``Request``; session cookies and
``request.user`` come from Django's middleware stack via
``BoltAPI(django_middleware=True)``.

Reads/writes go through the Django async ORM (``afirst``/``acount``/
``asave``/…).  Only the few pieces with no Django async equivalent —
``django.contrib.auth`` helpers, model/manager methods (``create_user``,
``set_password``, ``touch_login``, …) and the payment/booking/notification
services — hop to a worker thread through :func:`in_thread`.
"""

from __future__ import annotations

from typing import Any

import msgspec
from asgiref.sync import sync_to_async
from django_bolt.exceptions import HTTPException


async def in_thread(fn, *args, **kwargs):
    """Run a synchronous Django helper off the event loop.

    Django keeps its ``thread_sensitive`` executor on a single thread, so
    service calls (``create_booking``, ``pay_booking``, ``mark_all_seen``, …)
    and manager helpers that lack async equivalents run here without raising
    ``SynchronousOnlyOperation``.
    """

    return await sync_to_async(fn, thread_sensitive=True)(*args, **kwargs)


def _session_get(request: Any, key: str, default=None):
    return request.session.get(key, default)


def _session_set(request: Any, key: str, value: Any) -> None:
    request.session[key] = value


def _session_pop(request: Any, key: str, default=None):
    return request.session.pop(key, default)


async def session_get(request: Any, key: str, default=None):
    """Read a Django session value without blocking the async handler."""
    return await in_thread(_session_get, request, key, default)


async def session_set(request: Any, key: str, value: Any) -> None:
    """Write a Django session value without blocking the async handler."""
    await in_thread(_session_set, request, key, value)


async def session_pop(request: Any, key: str, default=None):
    """Remove a Django session value without blocking the async handler."""
    return await in_thread(_session_pop, request, key, default)


def mark_full_request(api):
    """Force every route to buffer body/query/headers/cookies.

    Our handlers read those components inside shared helpers (``json_body``,
    ``q``, …).  Django-Bolt's static analyzer only inspects the handler body,
    so it can not see those accesses and optimises the request body away on
    the real server (``request.body`` arrives empty).  Mark the request
    components explicitly per route so the Rust runtime always parses them.
    """

    for route in getattr(api, "_routes", []):
        meta = api._handler_meta.get(route[2])
        if meta is not None:
            meta["needs_body"] = True
            meta["needs_query"] = True
            meta["needs_headers"] = True
            meta["needs_cookies"] = True


def _resolve_user(request: Any):
    """Sync read of ``request.user`` (may force a lazy authentication)."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


async def get_user(request: Any):
    """Return the authenticated user, or ``None`` for anonymous requests."""
    return await in_thread(_resolve_user, request)


async def login_required(request: Any):
    user = await get_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    return user


async def _require_role(request: Any, attribute: str):
    user = await login_required(request)
    if not getattr(user, attribute, False):
        raise HTTPException(status_code=403, detail=f"role_required:{attribute}")
    return user


async def renter_required(request: Any):
    return await _require_role(request, "is_renter")


async def owner_required(request: Any):
    return await _require_role(request, "is_owner")


async def superadmin_required(request: Any):
    return await _require_role(request, "is_superadmin_role")


def json_body(request: Any) -> dict:
    """Decode the request body as a JSON object (``{}`` when empty)."""
    raw = getattr(request, "body", b"") or b""
    if not raw:
        return {}
    try:
        data = msgspec.json.decode(raw)
    except msgspec.DecodeError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_json:{exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="expected_json_object")
    return data


def query(request: Any) -> dict:
    return dict(getattr(request, "query", {}) or {})


def param_int(request: Any, name: str) -> int:
    """Read an ``int`` path parameter.

    Handlers must take a single ``request`` argument (request-only mode):
    that is the only shape for which the Django-Bolt runtime reliably parses
    ``request.body`` / ``request.query`` on the production server, so path
    parameters are exposed via ``request.params`` instead of function args.
    """

    raw = (getattr(request, "params", {}) or {}).get(name, "")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="not_found") from exc


def q(request: Any, key: str, default: str = "") -> str:
    return (query(request).get(key) or default).strip()


def body_str(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return "" if value is None else str(value).strip()


def body_int(data: dict, key: str, default: int = 0) -> int:
    value = data.get(key, default)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid_integer:{key}") from exc


def body_bool(data: dict, key: str, default: bool = False) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def body_float(data: dict, key: str, default: float | None = None):
    value = data.get(key, default)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid_number:{key}") from exc


__all__ = [
    "body_bool",
    "body_float",
    "body_int",
    "body_str",
    "get_user",
    "in_thread",
    "json_body",
    "login_required",
    "owner_required",
    "param_int",
    "q",
    "query",
    "renter_required",
    "session_get",
    "session_pop",
    "session_set",
    "superadmin_required",
]
