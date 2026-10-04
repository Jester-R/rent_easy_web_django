from __future__ import annotations

from django.urls import path

from . import console

app_name = "console"

urlpatterns = [
    path("", console.dashboard, name="dashboard"),
    # users
    path("users/", console.users_list, name="users"),
    path("users/new/", console.user_create, name="user_create"),
    path("users/bulk-delete/", console.users_bulk_delete, name="users_bulk_delete"),
    path("users/<int:pk>/edit/", console.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", console.user_delete, name="user_delete"),
    # properties
    path("properties/", console.properties_list, name="properties"),
    path("properties/new/", console.property_create, name="property_create"),
    path("properties/bulk-delete/", console.properties_bulk_delete, name="properties_bulk_delete"),
    path("properties/<int:pk>/edit/", console.property_edit, name="property_edit"),
    path("properties/<int:pk>/delete/", console.property_delete, name="property_delete"),
    # bookings
    path("bookings/", console.bookings_list, name="bookings"),
    path("bookings/new/", console.booking_create, name="booking_create"),
    path("bookings/bulk-delete/", console.bookings_bulk_delete, name="bookings_bulk_delete"),
    path("bookings/<int:pk>/edit/", console.booking_edit, name="booking_edit"),
    path("bookings/<int:pk>/delete/", console.booking_delete, name="booking_delete"),
    # payments
    path("payments/", console.payments_list, name="payments"),
    path("payments/new/", console.payment_create, name="payment_create"),
    path("payments/bulk-delete/", console.payments_bulk_delete, name="payments_bulk_delete"),
    path("payments/<int:pk>/edit/", console.payment_edit, name="payment_edit"),
    path("payments/<int:pk>/delete/", console.payment_delete, name="payment_delete"),
    # refunds
    path("refunds/new/", console.refund_create, name="refund_create"),
    path("refunds/<int:pk>/process/", console.refund_process, name="refund_process"),
]
