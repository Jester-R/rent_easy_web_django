from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0019_telegramloginrequest")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="stripe_publishable_key",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="stripe_secret_key",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="stripe_webhook_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
