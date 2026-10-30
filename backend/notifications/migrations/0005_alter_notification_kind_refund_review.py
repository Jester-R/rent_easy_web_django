from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_alter_notification_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
                choices=[
                    ("booking_request", "Booking request"),
                    ("booking_update", "Booking update"),
                    ("booking_approved", "Booking approved"),
                    ("payment_received", "Payment received"),
                    ("refund_requested", "Refund requested"),
                    ("refund_processed", "Refund processed"),
                    ("refund_rejected", "Refund request rejected"),
                    ("payout_paid", "Payout paid"),
                    ("owner_approval_request", "Owner approval request"),
                    ("owner_approved", "Owner approved"),
                    ("owner_rejected", "Owner rejected"),
                    ("announcement", "Announcement"),
                ],
                db_index=True,
                max_length=24,
            ),
        ),
    ]
