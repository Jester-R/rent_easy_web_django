from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0017_platformsettings_aba_payway_merchant_id")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="telegram_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
