from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "property", "renter", "owner", "status", "monthly_rent", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["property__title", "renter__email", "owner__email"]
    list_select_related = ["property", "renter", "owner", "payment"]
    date_hierarchy = "created_at"
