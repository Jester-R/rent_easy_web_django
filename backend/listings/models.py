from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Count
from django.utils import timezone


class PropertyCategory(models.TextChoices):
    APARTMENT = "apartment", "Apartment"
    HOUSE = "house", "House"
    CONDO = "condo", "Condo"
    VILLA = "villa", "Villa"
    ROOM = "room", "Room"
    STUDIO = "studio", "Studio"
    OFFICE = "office", "Office"
    LAND = "land", "Land"


class PropertyQuerySet(models.QuerySet):
    def for_renter(self, user):
        """Hide confirmed rentals and the renter's existing active requests."""
        from bookings.models import Booking, BookingStatus

        confirmed = Booking.objects.filter(
            property__isnull=False, status=BookingStatus.CONFIRMED
        ).values_list("property_id", flat=True)
        queryset = self.filter(is_active=True).exclude(id__in=confirmed)
        if not user or not user.is_authenticated:
            return queryset
        blocked = Booking.objects.filter(
            renter=user,
            property__isnull=False,
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED, BookingStatus.CONFIRMED],
        ).values_list("property_id", flat=True)
        return queryset.exclude(id__in=blocked)

    def available(self):
        return self

    def with_stats(self):
        return self.annotate(
            favorite_count=Count("favorites", distinct=True),
            booking_count=Count("bookings", distinct=True),
        )


class Property(models.Model):
    is_active = models.BooleanField(default=True, db_index=True)
    title = models.CharField(max_length=160)
    location = models.CharField(max_length=160, db_index=True)
    price_per_month = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        db_index=True,
    )
    category = models.CharField(
        max_length=24, choices=PropertyCategory.choices, blank=True, db_index=True
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    images = models.JSONField(default=list, blank=True)
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PropertyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["location", "price_per_month"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.location})"

    def get_absolute_url(self) -> str:
        return f"/property/{self.pk}/"

    @property
    def price_display(self) -> str:
        return f"${float(self.price_per_month or 0):,.0f}"

    @property
    def location_label(self) -> str:
        return self.location or "—"

    @property
    def cover_image(self) -> str:
        images = self.images or []
        return images[0] if images else ""

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="favorites"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "property"], name="unique_favorite")
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.property_id}"
