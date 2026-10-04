from __future__ import annotations

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("read-all/", views.read_all, name="read_all"),
    path("mark-seen/", views.mark_seen, name="mark_seen"),
    path("badge/", views.badge, name="badge"),
    path("preview/", views.preview, name="preview"),
    path("<int:pk>/toggle-read/", views.toggle_read, name="toggle_read"),
]
