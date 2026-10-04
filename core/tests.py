"""End-to-end coverage for the seeded demo data and every write workflow."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from bookings.models import Booking, BookingStatus
from listings.models import Favorite, Property
from notifications.models import Notification
from payments.models import Payment, Refund

SUPERADMIN = {"email": "admin@fake.com", "password": "admin"}
OWNER = {"email": "owner@fake.com", "password": "owner"}
RENTER = {"email": "renter@fake.com", "password": "renter"}

PROPERTY_FIELDS = {
    "title": "Test Studio",
    "location": "Phnom Penh - Toul Kork",
    "price_per_month": "410.00",
    "bedrooms": "1",
    "bathrooms": "1",
    "description": "Created by the automated test suite.",
}


class SeededTestCase(TestCase):
    """Base class that loads the demo dataset used by the role portals."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", "--reset", stdout=StringIO())
        cls.admin = User.objects.get(email=SUPERADMIN["email"])
        cls.owner = User.objects.get(email=OWNER["email"])
        cls.renter = User.objects.get(email=RENTER["email"])
        cls.property = Property.objects.filter(owner=cls.owner).first()

    def login(self, creds):
        client = self.client_class()
        self.assertTrue(client.login(**creds))
        return client

    def free_property_for_renter(self) -> Property:
        """A property owned by :attr:`owner` that the renter has no active booking on."""
        blocked = Booking.objects.filter(
            renter=self.renter,
            status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
        ).values_list("property_id", flat=True)
        return Property.objects.filter(owner=self.owner).exclude(pk__in=list(blocked)).first()


class RouteSmokeTests(SeededTestCase):
    """Every page must render for every audience without a server error."""

    def _routes(self):
        booking = Booking.objects.filter(renter=self.renter).first() or Booking.objects.first()
        payment = Payment.objects.first()
        prop, bid, payid = self.property.pk, booking.pk, payment.pk
        return [
            "/",
            reverse("landing"),
            reverse("health"),
            reverse("login"),
            reverse("register"),
            reverse("renter_home"),
            reverse("owner_home"),
            reverse("console:dashboard"),
            reverse("listings:renter_browse"),
            reverse("listings:renter_favorites"),
            reverse("listings:public_detail", args=[prop]),
            reverse("listings:booking_request", args=[prop]),
            reverse("bookings:renter_list"),
            reverse("bookings:renter_detail", args=[bid]),
            reverse("bookings:renter_pay", args=[bid]),
            reverse("payments:renter_list"),
            reverse("payments:renter_detail", args=[payid]),
            reverse("listings:owner_list"),
            reverse("listings:owner_edit", args=[prop]),
            reverse("listings:owner_create"),
            reverse("bookings:owner_list"),
            reverse("bookings:owner_detail", args=[bid]),
            reverse("payments:owner_list"),
            reverse("payments:owner_detail", args=[payid]),
            reverse("notifications:feed"),
            reverse("console:users"),
            reverse("console:user_create"),
            reverse("console:user_edit", args=[self.owner.pk]),
            reverse("console:properties"),
            reverse("console:property_create"),
            reverse("console:property_edit", args=[prop]),
            reverse("console:bookings"),
            reverse("console:booking_create"),
            reverse("console:booking_edit", args=[bid]),
            reverse("console:payments"),
            reverse("console:payment_create"),
            reverse("console:payment_edit", args=[payid]),
            reverse("profile"),
        ]

    def test_pages_render_for_every_role(self):
        audiences = {
            "anonymous": None,
            "renter": self.login(RENTER),
            "owner": self.login(OWNER),
            "superadmin": self.login(SUPERADMIN),
        }
        failures = []
        for label, client in audiences.items():
            for url in self._routes():
                response = client.get(url) if client else self.client_class().get(url)
                if response.status_code >= 500:
                    failures.append(f"{label} {url} -> {response.status_code}")
        self.assertEqual(failures, [])

    def test_unknown_route_renders_404_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)


class RegistrationTests(TestCase):
    def test_register_then_choose_renter_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "New Tester",
                "username": "newtester",
                "email": "new.tester@fake.com",
                "password": "Secret123",
                "password_confirm": "Secret123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new.tester@fake.com")

        response = self.client.post(reverse("role_select"), {"role": Role.RENTER})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.RENTER)

        client = self.client_class()
        client.force_login(user)
        self.assertEqual(client.get(reverse("renter_home")).status_code, 200)


class BookingLifecycleTests(SeededTestCase):
    def test_request_approve_then_pay(self):
        renter = self.login(RENTER)
        owner = self.login(OWNER)
        prop = self.free_property_for_renter()

        response = renter.post(
            reverse("listings:booking_request", args=[prop.pk]),
            {
                "message": "I would like to move in next month.",
                "move_in_date": (date.today() + timedelta(days=21)).isoformat(),
                "lease_months": 12,
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(renter=self.renter, property=prop, status=BookingStatus.PENDING)

        owner.post(reverse("bookings:owner_approve", args=[booking.pk]), {"next": reverse("bookings:owner_list")})
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.APPROVED)
        self.assertIsNotNone(booking.approved_at)

        self.assertEqual(renter.get(reverse("bookings:renter_pay", args=[booking.pk])).status_code, 200)
        response = renter.post(
            reverse("bookings:renter_pay", args=[booking.pk]),
            {"method": Payment.Method.ABA, "simulate": "success", "next": reverse("bookings:renter_list")},
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertTrue(booking.is_paid)
        self.assertEqual(booking.payment.status, Payment.Status.SUCCESS)

    def test_approved_booking_cannot_be_cancelled(self):
        prop = self.free_property_for_renter()
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=prop.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=prop.price_per_month,
            lease_months=12,
        )
        renter = self.login(RENTER)
        response = renter.post(reverse("bookings:renter_cancel", args=[booking.pk]), {"next": reverse("bookings:renter_list")})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.APPROVED)

    def test_pending_booking_can_be_cancelled_by_renter(self):
        prop = self.free_property_for_renter()
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=prop.owner,
            status=BookingStatus.PENDING,
            monthly_rent=prop.price_per_month,
            lease_months=12,
        )
        renter = self.login(RENTER)
        renter.post(reverse("bookings:renter_cancel", args=[booking.pk]), {"next": reverse("bookings:renter_list")})
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_owner_cannot_approve_another_owners_booking(self):
        other = User.objects.get(email="sokha.owned@fake.com")
        prop = Property.objects.filter(owner=other).first()
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=other,
            status=BookingStatus.PENDING,
            monthly_rent=prop.price_per_month,
            lease_months=12,
        )
        owner = self.login(OWNER)
        response = owner.post(reverse("bookings:owner_approve", args=[booking.pk]))
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.PENDING)

    def test_favorite_toggle_adds_and_removes(self):
        renter = self.login(RENTER)
        prop = self.free_property_for_renter()
        Favorite.objects.filter(user=self.renter, property=prop).delete()
        url = reverse("listings:toggle_favorite", args=[prop.pk])

        renter.post(url, {"next": reverse("listings:renter_favorites")})
        self.assertTrue(Favorite.objects.filter(user=self.renter, property=prop).exists())

        renter.post(url, {"next": reverse("listings:renter_favorites")})
        self.assertFalse(Favorite.objects.filter(user=self.renter, property=prop).exists())


class ConsoleCrudTests(SeededTestCase):
    def setUp(self):
        self.admin = self.login(SUPERADMIN)

    def test_property_create_edit_delete(self):
        response = self.admin.post(reverse("console:property_create"), {**PROPERTY_FIELDS, "owner": str(self.owner.pk)})
        self.assertEqual(response.status_code, 302)
        prop = Property.objects.get(title=PROPERTY_FIELDS["title"])
        self.assertEqual(prop.owner, self.owner)

        self.admin.post(
            reverse("console:property_edit", args=[prop.pk]),
            {**PROPERTY_FIELDS, "title": "Test Studio v2", "price_per_month": "455.00", "bedrooms": "2", "bathrooms": "2", "owner": str(self.owner.pk)},
        )
        prop.refresh_from_db()
        self.assertEqual(prop.title, "Test Studio v2")
        self.assertEqual(prop.price_per_month, Decimal("455.00"))

        self.admin.post(reverse("console:property_delete", args=[prop.pk]), {"next": reverse("console:properties")})
        self.assertFalse(Property.objects.filter(pk=prop.pk).exists())

    def test_user_create_edit_and_bulk_delete(self):
        response = self.admin.post(
            reverse("console:user_create"),
            {
                "full_name": "Console Renter",
                "username": "consolerenter",
                "email": "console.renter@fake.com",
                "password": "Secret123",
                "role": Role.RENTER,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="console.renter@fake.com")
        self.assertEqual(user.role, Role.RENTER)

        self.admin.post(
            reverse("console:user_edit", args=[user.pk]),
            {"full_name": "Console Renter Renamed", "username": "consolerenter", "email": user.email, "role": Role.OWNER, "is_active": "on"},
        )
        user.refresh_from_db()
        self.assertEqual(user.role, Role.OWNER)

        self.admin.post(reverse("console:users_bulk_delete"), {"ids": [user.pk], "next": reverse("console:users")})
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_booking_create_and_edit(self):
        response = self.admin.post(
            reverse("console:booking_create"),
            {
                "property": str(self.property.pk),
                "renter": str(self.renter.pk),
                "owner": str(self.property.owner_id),
                "status": BookingStatus.PENDING,
                "monthly_rent": str(self.property.price_per_month),
                "lease_months": "12",
                "move_in_date": (date.today() + timedelta(days=30)).isoformat(),
                "note": "created in console",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.order_by("-created_at").first()
        self.assertEqual(booking.owner, self.property.owner)

        self.admin.post(
            reverse("console:booking_edit", args=[booking.pk]),
            {
                "status": BookingStatus.APPROVED,
                "monthly_rent": "500",
                "lease_months": "24",
                "move_in_date": (date.today() + timedelta(days=45)).isoformat(),
                "note": "edited",
            },
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.APPROVED)
        self.assertEqual(booking.monthly_rent, Decimal("500.00"))

    def test_payment_create_edit_and_refund_lifecycle(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.property.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=self.property.price_per_month,
            lease_months=12,
        )
        response = self.admin.post(
            reverse("console:payment_create"),
            {
                "property": str(self.property.pk),
                "booking": str(booking.pk),
                "user": str(self.renter.pk),
                "amount": "500",
                "method": Payment.Method.WING,
                "status": Payment.Status.SUCCESS,
            },
        )
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.order_by("-created_at").first()

        self.admin.post(
            reverse("console:payment_edit", args=[payment.pk]),
            {
                "amount": "525",
                "method": Payment.Method.CARD,
                "status": Payment.Status.SUCCESS,
                "refund_status": Payment.RefundStatus.NONE,
                "refunded_amount": "0",
            },
        )
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("525.00"))
        self.assertEqual(payment.method, Payment.Method.CARD)

        self.admin.post(reverse("console:refund_create"), {"payment": str(payment.pk), "reason": Refund.Reason.OTHER})
        refund = Refund.objects.get(payment=payment)
        self.assertEqual(refund.status, Refund.Status.PENDING)

        self.admin.post(reverse("console:refund_process", args=[refund.pk]))
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)

    def test_non_superadmin_cannot_reach_console(self):
        renter = self.login(RENTER)
        for url in (reverse("console:dashboard"), reverse("console:users"), reverse("console:property_create")):
            response = renter.get(url)
            self.assertIn(response.status_code, (302, 403))


class PreferencesTests(SeededTestCase):
    def test_language_switch_renders_khmer(self):
        renter = self.login(RENTER)
        response = renter.post(reverse("set_language"), {"language": "km", "next": reverse("renter_home")})
        self.assertEqual(response.status_code, 302)
        html = renter.get(reverse("renter_home")).content.decode()
        self.assertTrue(any("\u1780" <= char <= "\u17ff" for char in html), "expected Khmer glyphs")

    def test_theme_switch_sets_cookie(self):
        renter = self.login(RENTER)
        response = renter.post(reverse("set_theme"), {"theme": "dark", "next": reverse("renter_home")})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(renter.cookies["renteasy_theme"].value, "dark")


class NotificationTests(SeededTestCase):
    def test_approval_and_payment_notifications_reach_the_renter(self):
        before = Notification.objects.filter(recipient=self.renter).count()
        prop = self.free_property_for_renter()
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=prop.owner,
            status=BookingStatus.PENDING,
            monthly_rent=prop.price_per_month,
            lease_months=12,
        )
        self.login(OWNER).post(reverse("bookings:owner_approve", args=[booking.pk]))
        self.assertGreater(Notification.objects.filter(recipient=self.renter).count(), before)

    def test_mark_all_read_clears_unread(self):
        self.login(RENTER).post(reverse("notifications:read_all"))
        self.assertFalse(Notification.objects.filter(recipient=self.renter, read_at__isnull=True).exists())
