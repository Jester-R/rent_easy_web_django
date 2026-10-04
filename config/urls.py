from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from accounts import dashboards
from accounts.views import (
    deny,
    home_router,
    login_view,
    logout_view,
    profile_view,
    register_view,
    role_select_view,
    set_language_view,
    set_theme_view,
)
from core import views as core_views

urlpatterns = [
    path("", home_router, name="home"),
    path("core/landing/", core_views.landing, name="landing"),
    path("core/health/", core_views.health, name="health"),
    path("core/tour/", core_views.dismiss_tour, name="dismiss_tour"),
    # -- auth ---------------------------------------------------------
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    path("auth/register/", register_view, name="register"),
    path("auth/role/", role_select_view, name="role_select"),
    path("auth/preferences/", profile_view, name="profile"),
    path("auth/denied/", deny, name="denied"),
    # -- preferences --------------------------------------------------
    path("i18n/set/", set_language_view, name="set_language"),
    path("theme/set/", set_theme_view, name="set_theme"),
    # -- role dashboards ----------------------------------------------
    path("rent/", dashboards.renter_dashboard, name="renter_home"),
    path("owner/", dashboards.owner_dashboard, name="owner_home"),
    # -- apps ---------------------------------------------------------
    path("", include("listings.urls")),
    path("", include("bookings.urls")),
    path("", include("payments.urls")),
    path("notifications/", include("notifications.urls")),
    path("console/", include(("accounts.console_urls", "console"), namespace="console")),
    path("dj-admin/", admin.site.urls),
]

handler403 = "core.views.permission_denied"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
