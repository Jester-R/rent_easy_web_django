from decimal import Decimal

from django.db import migrations, models


def copy_existing_gross_amounts(apps, schema_editor):
    Payout = apps.get_model("payments", "Payout")
    for payout in Payout.objects.all().iterator():
        payout.gross_amount = payout.amount
        payout.save(update_fields=["gross_amount"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_platformsettings_commission_rates_updated_at"),
        ("payments", "0005_refund_request_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="payout",
            name="gross_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10),
        ),
        migrations.AddField(
            model_name="payout",
            name="commission_rate",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5),
        ),
        migrations.AddField(
            model_name="payout",
            name="commission_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10),
        ),
        migrations.RunPython(copy_existing_gross_amounts, migrations.RunPython.noop),
    ]
