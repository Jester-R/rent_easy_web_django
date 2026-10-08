from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="property",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]
