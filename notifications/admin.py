from django.contrib import admin

from .models import Notification, NotificationSeen


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title_key", "kind", "recipient", "created_at", "read_at"]
    list_filter = ["kind", "read_at"]
    search_fields = ["recipient__email", "title_key"]
    list_select_related = ["recipient"]


@admin.register(NotificationSeen)
class NotificationSeenAdmin(admin.ModelAdmin):
    list_display = ["user", "seen_at"]
