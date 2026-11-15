from django.db import migrations


def confirm_paid_bookings(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    Booking.objects.filter(status="Approved", payment__isnull=False).update(
        status="Confirmed"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0005_booking_lease_months_default_one"),
    ]

    operations = [
        migrations.RunPython(confirm_paid_bookings, migrations.RunPython.noop),
    ]
