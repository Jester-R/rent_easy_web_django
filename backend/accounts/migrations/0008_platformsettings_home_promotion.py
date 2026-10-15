from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_alter_user_avatar_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsettings",
            name="home_promotion",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
