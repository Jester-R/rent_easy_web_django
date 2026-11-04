from django.db import migrations, models


def copy_existing_payout_details(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(payout_method="").iterator():
        if not (user.payout_account_name or user.payout_account_number):
            continue
        user.payout_accounts = {
            user.payout_method: {
                "account_name": user.payout_account_name,
                "account_number": user.payout_account_number,
                "bank_name": user.payout_bank_name,
                "phone": user.payout_phone,
                "note": user.payout_note,
            }
        }
        user.save(update_fields=["payout_accounts"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0014_platformsettings_payment_method_details")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="payout_accounts",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copy_existing_payout_details, migrations.RunPython.noop),
    ]
