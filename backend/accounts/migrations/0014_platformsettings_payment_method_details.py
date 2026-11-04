from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0013_platformsettings_commission_rates_updated_at")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="payment_method_details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
