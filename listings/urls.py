from __future__ import annotations

from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    # ---- renter screens -------------------------------------------
    path("rent/properties/", views.renter_browse, name="renter_browse"),
    path("rent/favorites/", views.renter_favorites, name="renter_favorites"),
    path("rent/property/<int:pk>/", views.renter_detail, name="detail"),
    path("rent/property/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("rent/property/<int:pk>/request/", views.booking_request, name="booking_request"),
    # ---- owner screens --------------------------------------------
    path("owner/properties/", views.owner_list, name="owner_list"),
    path("owner/properties/new/", views.owner_create, name="owner_create"),
    path("owner/properties/<int:pk>/edit/", views.owner_edit, name="owner_edit"),
    path("owner/properties/<int:pk>/delete/", views.owner_delete, name="owner_delete"),
    # ---- public ----------------------------------------------------
    path("property/<int:pk>/", views.public_detail, name="public_detail"),
]
