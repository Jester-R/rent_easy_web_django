from django.contrib import admin

from .models import Favorite, Property


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["title", "location", "price_per_month", "bedrooms", "bathrooms", "owner", "created_at"]
    list_filter = ["location", "bedrooms", "bathrooms"]
    search_fields = ["title", "location", "description", "owner__email"]
    autocomplete_fields = ["owner"]
    list_select_related = ["owner"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "property", "created_at"]
    search_fields = ["user__email", "property__title"]
    list_select_related = ["user", "property"]
