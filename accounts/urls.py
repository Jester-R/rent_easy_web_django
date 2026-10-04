from __future__ import annotations

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("role/", views.role_select_view, name="role_select"),
    path("profile/", views.profile_view, name="profile"),
    path("denied/", views.deny, name="denied"),
]
