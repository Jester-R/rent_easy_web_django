from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_user_is_email_verified_emailverification")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="telegram_chat_id",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="telegram_link_token",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="telegram_link_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
