from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0020_platformsettings_stripe_keys")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="aba_payway_api_key",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="google_oauth_client_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="google_oauth_client_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="google_oauth_redirect_uri",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_bot_token",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_bot_username",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_webhook_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_webhook_url",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_chat_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="platformsettings",
            name="telegram_login_auth_url",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
