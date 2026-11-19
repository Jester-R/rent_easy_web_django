from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def split_refund_chats(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    Message = apps.get_model("chat", "Message")
    User = apps.get_model("accounts", "User")

    admin = (
        User.objects.filter(is_active=True)
        .filter(Q(role="superadmin") | Q(is_staff=True) | Q(is_superuser=True))
        .order_by("pk")
        .first()
    )

    for conversation in Conversation.objects.filter(refund__isnull=False).iterator():
        booking = conversation.refund.booking
        if booking is None:
            continue
        conversation.refund_party = "renter"
        conversation.refund_participant_id = booking.renter_id
        conversation.support_admin_id = admin.pk if admin else None
        conversation.save(
            update_fields=["refund_party", "refund_participant", "support_admin"]
        )

        if Conversation.objects.filter(
            refund_id=conversation.refund_id, refund_party="owner"
        ).exists():
            continue
        owner_chat = Conversation.objects.create(
            property_id=conversation.property_id,
            renter_id=conversation.renter_id,
            owner_id=conversation.owner_id,
            refund_id=conversation.refund_id,
            refund_party="owner",
            refund_participant_id=booking.owner_id,
            support_admin_id=admin.pk if admin else None,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for message in conversation.messages.all().iterator():
            Message.objects.create(
                conversation_id=owner_chat.pk,
                sender_id=message.sender_id,
                body=message.body,
                created_at=message.created_at,
                read_at=message.read_at,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0002_remove_conversation_unique_conversation_participants_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="refund",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="payments.refund",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="refund_party",
            field=models.CharField(
                blank=True,
                choices=[("renter", "Renter"), ("owner", "Owner")],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="refund_participant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="refund_support_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="support_admin",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="refund_support_admin_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(split_refund_chats, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("refund__isnull", False)),
                fields=("refund", "refund_party"),
                name="unique_refund_support_chat_per_party",
            ),
        ),
    ]
