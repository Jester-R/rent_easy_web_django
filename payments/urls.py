from __future__ import annotations

from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # renter
    path("rent/payments/", views.renter_list, name="renter_list"),
    path("rent/payments/<int:pk>/", views.renter_detail, name="renter_detail"),
    # owner
    path("owner/payments/", views.owner_list, name="owner_list"),
    path("owner/payments/<int:pk>/", views.owner_detail, name="owner_detail"),
    path("owner/payments/refunds/<int:pk>/process/", views.process_refund_view, name="process_refund"),
]
