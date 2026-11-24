from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone


class PropertyOwnerStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    UNAVAILABLE = "unavailable", "Unavailable"
    REMOVED = "removed", "Removed"


class PropertyCategory(models.TextChoices):
    APARTMENT = "apartment", "Apartment"
    HOUSE = "house", "House"
    CONDO = "condo", "Condo"
    VILLA = "villa", "Villa"
    ROOM = "room", "Room"
    STUDIO = "studio", "Studio"
    OFFICE = "office", "Office"
    LAND = "land", "Land"


def active_paid_property_ids(property_ids=None):
    """Property IDs with an active, unreimbursed successful booking payment."""
    from bookings.models import ACTIVE_STATUSES, Booking
    from payments.models import Payment, Refund

    queryset = (
        Booking.objects.filter(
            status__in=ACTIVE_STATUSES,
            payment__status=Payment.Status.SUCCESS,
        )
        .exclude(
            payment__refunds__status__in=(
                Refund.Status.ACCEPTED,
                Refund.Status.PROCESSED,
            )
        )
        .exclude(end_date__lt=timezone.localdate())
    )
    if property_ids is not None:
        queryset = queryset.filter(property_id__in=property_ids)
    return queryset.values_list("property_id", flat=True)


def _active_reservations(property_ids=None):
    """Bookings that currently reserve a property without a successful payment."""
    from bookings.models import Booking, BookingStatus, payment_window_hours
    from payments.models import Payment

    hours = payment_window_hours()
    queryset = (
        Booking.objects.filter(
            property__isnull=False,
            status__in=(BookingStatus.PENDING, BookingStatus.APPROVED),
            created_at__gte=timezone.now() - timedelta(hours=hours),
        )
        .filter(Q(payment__isnull=True) | ~Q(payment__status=Payment.Status.SUCCESS))
    )
    if property_ids is not None:
        queryset = queryset.filter(property_id__in=property_ids)
    return queryset


def active_reservation_property_ids(property_ids=None):
    """Property IDs with an active unpaid reservation."""
    return (
        _active_reservations(property_ids)
        .values_list("property_id", flat=True)
        .distinct()
    )


def active_reservation_deadlines(property_ids=None) -> dict[int, str]:
    """Deadlines for active unpaid reservations, keyed by property ID.

    A reservation is an unpaid ``Pending``/``Approved`` booking inside the
    payment window. It is visible to other renters and blocks new bookings,
    but it does not hide the listing like a paid booking does.
    """
    from bookings.models import payment_window_hours

    hours = payment_window_hours()
    queryset = _active_reservations(property_ids)

    deadlines: dict[int, object] = {}
    for property_id, created_at in queryset.values_list("property_id", "created_at"):
        deadline = created_at + timedelta(hours=hours)
        current = deadlines.get(property_id)
        if current is None or deadline > current:
            deadlines[property_id] = deadline
    return {
        property_id: deadline.isoformat()
        for property_id, deadline in deadlines.items()
    }


class PropertyQuerySet(models.QuerySet):
    def for_renter(self, user):
        """Hide confirmed/paid rentals from every renter.

        Unpaid reservations stay visible to everyone; they are reported as
        reserved by the API and block new booking requests until paid,
        expired, or released by the owner. A renter who cancelled a request
        still sees the listing again - the rebook cooldown only blocks the
        submit action in ``create_booking``.
        """
        from bookings.models import Booking, BookingStatus

        confirmed = Booking.objects.filter(
            property__isnull=False,
            status=BookingStatus.CONFIRMED,
        ).exclude(end_date__lt=timezone.localdate()).values_list("property_id", flat=True)
        return (
            self.filter(is_active=True)
            .exclude(id__in=confirmed)
            .exclude(id__in=active_paid_property_ids())
        )

    def available(self):
        return self

    def with_stats(self):
        return self.annotate(
            favorite_count=Count("favorites", distinct=True),
            booking_count=Count("bookings", distinct=True),
        )


class Property(models.Model):
    is_active = models.BooleanField(default=True, db_index=True)
    owner_status = models.CharField(
        max_length=16,
        choices=PropertyOwnerStatus.choices,
        default=PropertyOwnerStatus.AVAILABLE,
        db_index=True,
    )
    rental_closed_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=160)
    title_km = models.CharField(max_length=160, blank=True, default="")
    province = models.CharField(max_length=160, blank=True, default="", db_index=True)
    province_km = models.CharField(max_length=160, blank=True, default="")
    location = models.CharField(max_length=160, db_index=True)
    location_km = models.CharField(max_length=160, blank=True, default="")
    commune = models.CharField(max_length=160, blank=True, default="", db_index=True)
    commune_km = models.CharField(max_length=160, blank=True, default="")
    village = models.CharField(max_length=160, blank=True, default="", db_index=True)
    village_km = models.CharField(max_length=160, blank=True, default="")
    price_per_month = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        db_index=True,
    )
    category = models.CharField(max_length=24, blank=True, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    images = models.JSONField(default=list, blank=True)
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    description_km = models.TextField(blank=True, default="")
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


class OwnerPropertyAction(models.Model):
    class Action(models.TextChoices):
        UNAVAILABLE = "unavailable", "Marked unavailable"
        REMOVE = "remove", "Removed listing"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_actions",
    )
    property = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "action", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.property_id}"
