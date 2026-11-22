from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0006_confirm_paid_bookings")]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="expired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("Pending", "Pending"),
                    ("Approved", "Approved"),
                    ("Confirmed", "Confirmed"),
                    ("Rejected", "Rejected"),
                    ("Cancelled", "Cancelled"),
                    ("Expired", "Expired"),
                ],
                db_index=True,
                default="Pending",
                max_length=16,
            ),
        ),
    ]
