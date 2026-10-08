from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0002_initial")]

    operations = [
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
                ],
                db_index=True,
                default="Pending",
                max_length=16,
            ),
        ),
    ]
