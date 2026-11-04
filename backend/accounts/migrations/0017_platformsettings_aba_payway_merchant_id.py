from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0016_user_payment_details")]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="aba_payway_merchant_id",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
