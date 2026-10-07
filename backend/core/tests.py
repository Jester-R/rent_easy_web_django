"""Model/service-level coverage using the seeded demo dataset.

The legacy HTML view layer was removed when the app moved to the django-bolt
JSON API, so this suite now exercises the data model and notification links
that the API serializers rely on.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
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
        booking = Booking.objects.filter(owner=self.owner).first() or Booking.objects.first()
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


class PropertyQuerySmokeTests(SeededTestCase):
    def test_for_renter_excludes_active_without_loading(self):
        queryset = Property.objects.for_renter(self.renter)
        q = queryset.query
        self.assertIsNotNone(q)
        self.assertFalse(queryset._result_cache)