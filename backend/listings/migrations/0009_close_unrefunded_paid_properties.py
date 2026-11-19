from __future__ import annotations

from django.db import migrations
from django.utils import timezone


def close_unrefunded_paid_properties(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    Property = apps.get_model("listings", "Property")

    paid_property_ids = (
        Booking.objects.filter(payment__status="Success")
        .exclude(payment__refunds__status__in=("Accepted", "Processed"))
        .exclude(end_date__lt=timezone.localdate())
        .values_list("property_id", flat=True)
    )
    (
        Property.objects.filter(pk__in=paid_property_ids)
        .exclude(owner_status="removed")
        .update(
            is_active=False,
            rental_closed_at=timezone.now(),
            owner_status="unavailable",
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0008_property_owner_status_ownerpropertyaction"),
        ("bookings", "0008_alter_booking_lease_months"),
        ("payments", "0012_alter_payment_status"),
    ]

    operations = [
        migrations.RunPython(close_unrefunded_paid_properties, migrations.RunPython.noop),
    ]
