from __future__ import annotations

from django.db import migrations
from django.utils import timezone


def reopen_cancelled_paid_properties(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    Property = apps.get_model("listings", "Property")

    active_paid_property_ids = (
        Booking.objects.filter(
            status__in=("Pending", "Approved", "Confirmed"),
            payment__status="Success",
        )
        .exclude(payment__refunds__status__in=("Accepted", "Processed"))
        .exclude(end_date__lt=timezone.localdate())
        .values_list("property_id", flat=True)
    )
    (
        Property.objects.filter(
            owner_status="unavailable", rental_closed_at__isnull=False
        )
        .exclude(pk__in=active_paid_property_ids)
        .update(
            is_active=True,
            rental_closed_at=None,
            owner_status="available",
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0009_close_unrefunded_paid_properties"),
    ]

    operations = [
        migrations.RunPython(reopen_cancelled_paid_properties, migrations.RunPython.noop),
    ]
