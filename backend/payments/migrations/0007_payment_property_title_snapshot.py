from django.db import migrations, models


def backfill_property_titles(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    for payment in Payment.objects.select_related("property", "booking").iterator():
        title = ""
        if payment.property_id and payment.property:
            title = payment.property.title
        elif payment.booking_id and payment.booking:
            booking_property_id = payment.booking.property_id
            if booking_property_id:
                title = payment.booking.property.title
        if not title:
            payload = (
                payment.gateway_payload
                if isinstance(payment.gateway_payload, dict)
                else {}
            )
            request = (
                payload.get("request")
                if isinstance(payload.get("request"), dict)
                else {}
            )
            items = (
                request.get("items") if isinstance(request.get("items"), list) else []
            )
            if items and isinstance(items[0], dict):
                title = str(items[0].get("name") or "")[:160]
        if title:
            Payment.objects.filter(pk=payment.pk).update(
                property_title_snapshot=title[:160]
            )


class Migration(migrations.Migration):
    dependencies = [("payments", "0006_payout_commission")]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="property_title_snapshot",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.RunPython(backfill_property_titles, migrations.RunPython.noop),
    ]
