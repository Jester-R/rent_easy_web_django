"""Model/service-level coverage using the seeded demo dataset.

The legacy HTML view layer was removed when the app moved to the django-bolt
JSON API, so this suite now exercises the data model and notification links
that the API serializers rely on.
"""

from __future__ import annotations

import json as json_module
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
from core.ai import (
    _parse_json_object,
    build_property_description_prompt,
    generate_property_description,
)
from core.bolt_serializers import BookingSerializer, _needs_plan_reload
from listings.models import Property
from notifications.models import Notification
from payments.models import Payment, Refund

SUPERADMIN = {"email": "admin@fake.com", "password": "admin"}
OWNER = {"email": "owner@fake.com", "password": "owner"}
RENTER = {"email": "renter@fake.com", "password": "renter"}


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", "--reset", stdout=StringIO())
        cls.admin = User.objects.get(email=SUPERADMIN["email"])
        cls.owner = User.objects.get(email=OWNER["email"])
        cls.renter = User.objects.get(email=RENTER["email"])

    def free_property_for_renter(self) -> Property:
        blocked = Booking.objects.filter(
            renter=self.renter,
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        ).values_list("property_id", flat=True)
        return (
            Property.objects.filter(owner=self.owner)
            .exclude(pk__in=list(blocked))
            .first()
        )


class SeedSmokeTests(SeededTestCase):
    def test_seed_counts(self):
        self.assertEqual(User.objects.count(), 10)
        self.assertEqual(Property.objects.count(), 10)
        self.assertGreaterEqual(Booking.objects.count(), 5)
        self.assertGreaterEqual(Payment.objects.count(), 1)
        self.assertEqual(self.admin.role, Role.SUPERADMIN)
        self.assertEqual(self.owner.role, Role.OWNER)
        self.assertEqual(self.renter.role, Role.RENTER)

    def test_demo_logins(self):
        self.client.login(**SUPERADMIN)
        self.client.login(**OWNER)
        self.client.login(**RENTER)


class ModelLinkTests(SeededTestCase):
    def test_booking_links(self):
        booking = (
            Booking.objects.filter(owner=self.owner).first() or Booking.objects.first()
        )
        self.assertEqual(booking.get_absolute_url(), f"/rent/bookings/{booking.pk}/")
        booking._viewer = self.owner
        self.assertEqual(booking.get_absolute_url(), f"/owner/bookings/{booking.pk}/")

    def test_property_and_payment_links(self):
        prop = Property.objects.first()
        self.assertEqual(prop.get_absolute_url(), f"/property/{prop.pk}/")
        payment = Payment.objects.first()
        self.assertEqual(payment.get_absolute_url(), f"/rent/payments/{payment.pk}/")

    def test_notification_link_fallback(self):
        self.assertEqual(
            Notification.get_absolute_url(Notification(link="")), "/notifications/"
        )
        self.assertEqual(
            Notification.get_absolute_url(Notification(link="/rent/")), "/rent/"
        )

    def test_payment_property_title(self):
        payment = Payment.objects.select_related("property").first()
        self.assertEqual(
            payment.property_title,
            payment.property.title,
        )
        refund = Refund.objects.first()
        if refund is not None:
            self.assertEqual(
                refund.payment.get_absolute_url(),
                f"/rent/payments/{refund.payment_id}/",
            )


class BookingSerializerPlanTests(SeededTestCase):
    def test_plan_loads_payment_and_payout_for_async_serialization(self):
        booking = (
            Booking.objects.select_related("property", "renter", "owner")
            .filter(payment__isnull=False)
            .first()
        )
        self.assertIsNotNone(booking)
        plan = BookingSerializer.loading_plan(Booking)
        self.assertIn("payment", plan.select_related)
        self.assertIn("payment__payout", plan.select_related)
        self.assertTrue(_needs_plan_reload(booking, plan))

        reloaded = BookingSerializer._prepare_queryset(
            Booking.objects.filter(pk=booking.pk)
        ).get()
        self.assertIn("payment", reloaded._state.fields_cache)
        self.assertFalse(_needs_plan_reload(reloaded, plan))


class PropertyQuerySmokeTests(SeededTestCase):
    def test_for_renter_excludes_active_without_loading(self):
        queryset = Property.objects.for_renter(self.renter)
        q = queryset.query
        self.assertIsNotNone(q)
        self.assertFalse(queryset._result_cache)


class _FakeGroqResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class _FakeGroqClient:
    response_payload = {}
    last_request = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).last_request = json
        content = json_module.dumps(type(self).response_payload)
        return _FakeGroqResponse(
            {"choices": [{"message": {"content": content}}]}
        )


class AIDescriptionTests(TestCase):
    def test_prompt_contains_provided_facts_and_json_instruction(self):
        messages = build_property_description_prompt(
            {
                "title": "Sunny Studio",
                "location": "Phnom Penh - BKK1",
                "price_per_month": 300,
                "notes": "Balcony and parking",
            }
        )
        system = messages[0]["content"]
        user = messages[1]["content"]
        self.assertIn("JSON", system)
        self.assertIn("never invent", system.lower())
        self.assertIn("Sunny Studio", user)
        self.assertIn("Phnom Penh - BKK1", user)
        self.assertIn("Balcony and parking", user)

    def test_parse_json_object_accepts_fenced_json(self):
        data = _parse_json_object(
            '```json\n{"description": "English", "description_km": "ខ្មែរ"}\n```'
        )
        self.assertEqual(data["description"], "English")
        self.assertEqual(data["description_km"], "ខ្មែរ")

    def test_parse_json_object_rejects_invalid_content(self):
        with self.assertRaises(ValueError):
            _parse_json_object("no json here")

    @patch.dict(
        "os.environ",
        {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "test-model"},
        clear=False,
    )
    @patch("core.ai.httpx.AsyncClient", _FakeGroqClient)
    async def test_generate_property_description_returns_both_languages(self):
        _FakeGroqClient.response_payload = {
            "description": "A bright studio in BKK1.",
            "description_km": "ស្ទូឌីយោភ្លឺនៅ BKK1។",
        }
        result = await generate_property_description(
            {"title": "Sunny Studio", "location": "Phnom Penh - BKK1"}
        )

        self.assertEqual(result["description"], "A bright studio in BKK1.")
        self.assertEqual(result["description_km"], "ស្ទូឌីយោភ្លឺនៅ BKK1។")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(_FakeGroqClient.last_request["model"], "test-model")
        self.assertEqual(
            _FakeGroqClient.last_request["response_format"], {"type": "json_object"}
        )
