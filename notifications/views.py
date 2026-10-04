from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import http_methods

from .models import Notification
from .services import mark_all_seen, notify, recent_for, unread_count


@require_GET
@login_required
def feed(request):
    items = list(recent_for(request.user, limit=60))
    mark_all_seen(request.user)
    return render(
        request,
        "notifications/feed.html",
        {"notifications": items, "unread_count": 0},
    )


@require_POST
@login_required
def read_all(request):
    mark_all_seen(request.user)
    return redirect(request.POST.get("next") or "notifications:feed")


@require_POST
@login_required
def toggle_read(request, pk: int):
    item = Notification.objects.filter(pk=pk, recipient=request.user).first()
    if item:
        item.mark_read()
    return HttpResponse(status=204)


@require_GET
@login_required
def badge(request):
    return JsonResponse({"unread": unread_count(request.user)})


@require_GET
def preview(request):
    """Live dropdown payload for the bell (fetched with jQuery)."""
    items = []
    for item in recent_for(request.user, limit=12):
        items.append(
            {
                "id": item.pk,
                "title": item.title_key,
                "body": item.body_key,
                "params": item.params,
                "link": item.link,
                "action": item.action,
                "kind": item.kind,
                "read": item.is_read,
                "created_at": item.created_at.isoformat(),
            }
        )
    return JsonResponse({"items": items, "unread": unread_count(request.user)})


@http_methods("POST")
def mark_seen(request):
    mark_all_seen(request.user)
    return redirect(request.POST.get("next") or "notifications:feed")


__all__ = ["feed", "preview", "badge", "read_all", "mark_seen", "toggle_read", "notify"]
