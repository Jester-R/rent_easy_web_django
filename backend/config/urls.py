from __future__ import annotations

from django.contrib import admin
from django.urls import path

urlpatterns = [
    # Keep Django admin available when running Django with admin enabled.
    path("dj-admin/", admin.site.urls),
]
