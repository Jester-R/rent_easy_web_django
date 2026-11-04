from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0004_booking_end_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="lease_months",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
