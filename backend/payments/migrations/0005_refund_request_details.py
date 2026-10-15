from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_platformsettings_home_promotion"),
        ("payments", "0004_alter_refund_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="refund",
            name="request_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="refund",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="refund_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
