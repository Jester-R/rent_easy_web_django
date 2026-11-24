from django.db import migrations


DEFAULT_METHOD = "ABA Pay (Mock)"


def cleanup_legacy_payment_methods(apps, schema_editor):
    payment_model = apps.get_model("payments", "Payment")
    allowed = {
        value for value, _label in payment_model._meta.get_field("method").choices
    }
    payment_model.objects.exclude(method__in=allowed).update(method=DEFAULT_METHOD)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0012_alter_payment_status"),
    ]

    operations = [
        migrations.RunPython(cleanup_legacy_payment_methods, migrations.RunPython.noop),
    ]
