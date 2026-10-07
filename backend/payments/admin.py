from django.contrib import admin

from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "amount",
        "method",
        "status",
        "refund_status",
        "user",
        "created_at",
    ]
    list_filter = ["status", "refund_status", "method"]
    search_fields = ["reference", "user__email", "property__title"]
    list_select_related = ["user", "property", "booking"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["reference", "amount", "reason", "status", "payment", "created_at"]
    list_filter = ["status", "reason"]
    search_fields = ["reference"]
    list_select_related = ["payment", "booking"]
