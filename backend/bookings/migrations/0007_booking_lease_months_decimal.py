from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0006_confirm_paid_bookings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="lease_months",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.00"),
                max_digits=6,
            ),
        ),
    ]
