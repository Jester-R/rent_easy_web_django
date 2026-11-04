from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0011_user_telegram_link")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="commission_rates",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
