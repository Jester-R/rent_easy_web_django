from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0012_platformsettings_commission_rates")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="commission_rates_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
