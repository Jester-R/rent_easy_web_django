from __future__ import annotations

from functools import wraps

from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse


def http_methods(*methods):
    """Only allow the given HTTP verbs (mirrors the app's single-action screens).

    Accepts either varargs (``@http_methods("GET", "POST")``) or a single
    iterable (``@http_methods(["GET", "POST"])``).
    """
    if len(methods) == 1 and not isinstance(methods[0], str):
        methods = tuple(methods[0])
    allowed = {m.upper() for m in methods}
    if "GET" in allowed:
        allowed.add("HEAD")

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                return HttpResponseNotAllowed(sorted(allowed))
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


# Backwards-compatible alias used by some modules.
require_http_methods_ = http_methods


def redirect_to_login(request):
    from django.conf import settings

    login_url = reverse(settings.LOGIN_URL) if not settings.LOGIN_URL.startswith("/") else settings.LOGIN_URL
    nxt = request.get_full_path()
    return redirect(f"{login_url}?next={nxt}")


def role_guard(attribute: str):
    """Send signed-in users whose role does not match ``attribute`` to the 403 page."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request)
            if not getattr(user, attribute, False):
                return redirect(f"{reverse('denied')}?role={attribute}")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
