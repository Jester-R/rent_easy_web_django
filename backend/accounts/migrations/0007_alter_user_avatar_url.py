from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_platformsettings_notification_messages_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="avatar_url",
            field=models.TextField(blank=True),
        ),
    ]
