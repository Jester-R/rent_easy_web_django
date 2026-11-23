from django.db import migrations


DEFAULT_METHOD = "aba"


def cleanup_legacy_payout_methods(apps, schema_editor):
    user_model = apps.get_model("accounts", "User")
    allowed = {
        value
        for value, _label in user_model._meta.get_field("payout_method").choices
    }
    user_model.objects.exclude(payout_method__in=allowed).update(
        payout_method=DEFAULT_METHOD
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0024_platformsettings_late_cancellation_fee"),
    ]

    operations = [
        migrations.RunPython(cleanup_legacy_payout_methods, migrations.RunPython.noop),
    ]
