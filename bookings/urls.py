from __future__ import annotations

from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    # renter
    path("rent/bookings/", views.renter_list, name="renter_list"),
    path("rent/bookings/<int:pk>/", views.renter_detail, name="renter_detail"),
    path("rent/bookings/<int:pk>/cancel/", views.renter_cancel, name="renter_cancel"),
    path("rent/bookings/<int:pk>/pay/", views.renter_pay, name="renter_pay"),
    # owner
    path("owner/bookings/", views.owner_list, name="owner_list"),
    path("owner/bookings/<int:pk>/", views.owner_detail, name="owner_detail"),
    path("owner/bookings/<int:pk>/approve/", views.owner_approve, name="owner_approve"),
    path("owner/bookings/<int:pk>/reject/", views.owner_reject, name="owner_reject"),
]
