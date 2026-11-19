from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models


def round_existing_lease_months(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    for booking in Booking.objects.all():
        value = Decimal(str(booking.lease_months or 1)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        value = max(1, int(value))
        if value != booking.lease_months:
            booking.lease_months = value
            booking.save(update_fields=["lease_months"])


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0007_booking_lease_months_decimal"),
    ]

    operations = [
        migrations.RunPython(round_existing_lease_months, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="booking",
            name="lease_months",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
