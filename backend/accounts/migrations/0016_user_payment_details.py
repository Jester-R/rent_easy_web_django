from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0015_user_payout_accounts")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="payment_account_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="user",
            name="payment_account_number",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="payment_phone",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
