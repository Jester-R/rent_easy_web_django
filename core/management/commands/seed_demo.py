"""Populate the database with demo accounts, listings, bookings and payments.

Usage::

    python manage.py seed_demo            # create anything missing
    python manage.py seed_demo --reset    # wipe app data first
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog, Role, User
from bookings.models import Booking, BookingStatus
from listings.models import Favorite, Property
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment, Refund

SUPERADMIN = {"email": "admin@fake.com", "username": "admin", "password": "admin", "full_name": "RentEasy Admin"}

OWNERS = [
    ("owner@fake.com", "owner", "Demo Owner", 280, 560),
    ("dana.owned@fake.com", "dana", "Dana Chea", 320, 640),
    ("sokha.owned@fake.com", "sokha", "Sokha Lim", 260, 520),
    ("mara.owned@fake.com", "mara", "Mara Vann", 300, 700),
]

RENTERS = [
    ("renter@fake.com", "renter", "Demo Renter"),
    ("lida.rent@fake.com", "lida", "Lida Chou"),
    ("bora.rent@fake.com", "bora", "Bora Phal"),
    ("kev.rent@fake.com", "kev", "Kev Samang"),
    ("nara.rent@fake.com", "nara", "Nara Oum"),
]

LOCATIONS = [
    "Phnom Penh - BKK1",
    "Phnom Penh - Toul Kork",
    "Phnom Penh - Tuol Khmao",
    "Phnom Penh - Chroy Changvar",
    "Phnom Penh - Daun Penh",
    "Siem Reap - Wat Bo",
]

TITLES = [
    "Modern Studio Near Riverside",
    "Sunlit One Bedroom Apartment",
    "Quiet Corner Unit With Balcony",
    "Fully Furnished Loft",
    "Family Home Near Russian Market",
    "Studio With Workspace And A/C",
    "Garden Townhouse Two Bedrooms",
    "City View Apartment In Tower",
]

DESCRIPTIONS = [
    "Bright corner unit with natural light, reliable water and a secure door.",
    "Short walk to cafes and the market. Includes air conditioning and a fridge.",
    "Quiet building, friendly neighbours, parking space for one car.",
    "Recently renovated with new flooring, fresh paint and modern fittings.",
    "Furnished and ready to move in. Water and electricity are billed separately.",
]

AMENITIES_NOTE = [
    "Wifi ready, water heater installed, and a bicycle parking area.",
    "Air conditioning in every room plus a washing machine on the ground floor.",
    "Backup generator for the building and 24/7 security at the entrance.",
]


class Command(BaseCommand):
    help = "Create demo accounts, properties, bookings, payments and notifications."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing app data before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(20261004)

        if options["reset"]:
            self.stdout.write("Resetting application data…")
            for model in (Refund, Payment, Notification, Favorite, Booking, Property, AuditLog):
                model.objects.all().delete()
            User.objects.exclude(email=SUPERADMIN["email"]).delete()

        admin = self._ensure_superadmin()
        owners = [self._ensure_user(email, username, name, Role.OWNER, "owner" if username == "owner" else "owner123") for email, username, name, _, _ in OWNERS]
        renters = [self._ensure_user(email, username, name, Role.RENTER, "renter" if username == "renter" else "renter123") for email, username, name in RENTERS]

        properties = self._ensure_properties(owners, rng)
        self._ensure_favorites(renters, properties, rng)
        bookings = self._ensure_bookings(properties, renters, rng)
        self._ensure_payments(bookings, rng)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {User.objects.count()} users · {Property.objects.count()} properties · "
                f"{Booking.objects.count()} bookings · {Payment.objects.count()} payments · "
                f"{Refund.objects.count()} refunds"
            )
        )
        self.stdout.write(f"Superadmin login: {SUPERADMIN['username']} / {SUPERADMIN['password']}")
        self.stdout.write("Demo logins: owner / owner  ·  renter / renter")

    # -- accounts ------------------------------------------------------
    def _ensure_superadmin(self) -> User:
        user = User.objects.filter(email=SUPERADMIN["email"]).first()
        if user:
            return user
        return User.objects.create_superuser(
            email=SUPERADMIN["email"],
            username=SUPERADMIN["username"],
            password=SUPERADMIN["password"],
            full_name=SUPERADMIN["full_name"],
        )

    def _ensure_user(self, email: str, username: str, full_name: str, role: str, password: str) -> User:
        user = User.objects.filter(email=email).first()
        if user:
            return user
        return User.objects.create_user(
            email=email,
            username=username,
            password=password,
            full_name=full_name,
            role=role,
        )

    # -- listings ------------------------------------------------------
    def _ensure_properties(self, owners, rng) -> list[Property]:
        properties = list(Property.objects.select_related("owner"))
        if len(properties) >= 10:
            return properties
        start = len(properties)
        for index in range(start, 10):
            owner = owners[index % len(owners)]
            low, high = dict((o[0], (o[3], o[4])) for o in OWNERS)[owner.email]
            created = timezone.now() - timedelta(days=rng.randint(1, 90))
            properties.append(
                Property.objects.create(
                    title=TITLES[index % len(TITLES)],
                    location=LOCATIONS[index % len(LOCATIONS)],
                    price_per_month=Decimal(rng.randrange(low, high, 10)),
                    bedrooms=rng.choice([0, 1, 1, 2, 2, 3]),
                    bathrooms=rng.choice([1, 1, 2]),
                    description=f"{DESCRIPTIONS[index % len(DESCRIPTIONS)]} {AMENITIES_NOTE[index % len(AMENITIES_NOTE)]}",
                    owner=owner,
                    created_at=created,
                )
            )
        self.stdout.write(f"Created {10 - start} properties.")
        return properties

    def _ensure_favorites(self, renters, properties, rng) -> None:
        created = 0
        for renter in renters:
            for prop in rng.sample(properties, k=min(3, len(properties))):
                _, was_created = Favorite.objects.get_or_create(user=renter, property=prop)
                created += int(was_created)
        if created:
            self.stdout.write(f"Created {created} favorites.")

    # -- bookings ------------------------------------------------------
    def _ensure_bookings(self, properties, renters, rng) -> list[Booking]:
        if Booking.objects.exists():
            return list(Booking.objects.select_related("property", "renter", "owner"))
        plan = [
            (BookingStatus.PENDING, 3),
            (BookingStatus.APPROVED, 4),
            (BookingStatus.REJECTED, 2),
            (BookingStatus.CANCELLED, 1),
        ]
        bookings: list[Booking] = []
        prop_index = 0
        for status, count in plan:
            for _ in range(count):
                prop = properties[prop_index % len(properties)]
                prop_index += 1
                renter = rng.choice(renters)
                created = timezone.now() - timedelta(days=rng.randint(1, 45))
                booking = Booking.objects.create(
                    property=prop,
                    renter=renter,
                    owner=prop.owner,
                    status=status,
                    monthly_rent=prop.price_per_month,
                    lease_months=rng.choice([6, 12, 12, 24]),
                    move_in_date=(created + timedelta(days=rng.randint(5, 30))).date(),
                    note=rng.choice(
                        [
                            "I can move in within two weeks and can pay the deposit up front.",
                            "Interested in a long lease. Please consider my request.",
                            "Flexible on the move-in date, happy to sign this week.",
                            "",
                        ]
                    ),
                    created_at=created,
                )
                self._apply_timestamps(booking, status, created)
                bookings.append(booking)
        self.stdout.write(f"Created {len(bookings)} bookings.")
        return bookings

    def _apply_timestamps(self, booking: Booking, status: str, created) -> None:
        when = created + timedelta(hours=rng_hours(booking))
        fields = []
        if status == BookingStatus.APPROVED:
            booking.approved_at = when
            fields = ["approved_at"]
        elif status == BookingStatus.REJECTED:
            booking.rejected_at = when
            fields = ["rejected_at"]
        elif status == BookingStatus.CANCELLED:
            booking.cancelled_at = when
            fields = ["cancelled_at"]
        if fields:
            booking.save(update_fields=fields)

    # -- money ---------------------------------------------------------
    def _ensure_payments(self, bookings, rng) -> None:
        if Payment.objects.exists():
            return
        paid = [b for b in bookings if b.status in (BookingStatus.APPROVED, BookingStatus.CANCELLED)]
        created = 0
        for booking in paid:
            payment = Payment.objects.create(
                property=booking.property,
                user=booking.renter,
                booking=booking,
                amount=Decimal(booking.monthly_rent) * Decimal(1),
                method=booking.method if hasattr(booking, "method") else rng.choice(list(Payment.Method.values)),
                status=Payment.Status.SUCCESS,
                created_at=booking.approved_at or booking.created_at,
            )
            booking.payment = payment
            booking.save(update_fields=["payment"])
            created += 1
            if booking.status == BookingStatus.CANCELLED:
                refund = Refund.objects.create(
                    payment=payment,
                    booking=booking,
                    amount=payment.amount,
                    reason=Refund.Reason.CANCELLED_BY_RENTER,
                    status=Refund.Status.PENDING,
                    created_at=booking.cancelled_at or booking.created_at,
                )
                payment.refund_status = Payment.RefundStatus.PENDING
                payment.save(update_fields=["refund_status"])
                self.stdout.write(f"Created refund {refund.reference}.")
        failed = Booking.objects.filter(status=BookingStatus.REJECTED).first()
        if failed:
            Payment.objects.create(
                property=failed.property,
                user=failed.renter,
                booking=failed,
                amount=failed.monthly_rent,
                method=rng.choice(list(Payment.Method.values)),
                status=Payment.Status.FAILED,
                created_at=failed.created_at,
            )
            created += 1
        if created:
            self.stdout.write(f"Created {created} payments.")
        self._ensure_notifications(bookings)

    def _ensure_notifications(self, bookings) -> None:
        if Notification.objects.exists():
            return
        count = 0
        for booking in Booking.objects.select_related("property", "renter", "owner")[:12]:
            params = {
                "title": booking.property_title,
                "renter": booking.renter.display_name,
                "amount": booking.rent_display,
                "status": booking.status,
            }
            if booking.status == BookingStatus.PENDING:
                notify(
                    booking.owner,
                    Notification.Kind.BOOKING_REQUEST,
                    "notif_new_request",
                    "notif_new_request_body",
                    params=params,
                    link=f"/rent/bookings/{booking.pk}/",
                    action="approve",
                )
                notify(
                    booking.renter,
                    Notification.Kind.BOOKING_REQUEST,
                    "notif_booking_update",
                    "booking_sent",
                    params=params,
                    link=f"/rent/bookings/{booking.pk}/",
                )
                count += 2
            elif booking.payment_id:
                notify(
                    booking.owner,
                    Notification.Kind.PAYMENT_RECEIVED,
                    "notif_payment_received",
                    "notif_payment_received_body",
                    params=params,
                    link=f"/owner/payments/{booking.payment_id}/",
                )
                count += 1
        if count:
            self.stdout.write(f"Created {count} notifications.")


def rng_hours(booking: Booking) -> int:
    """Deterministic-ish offset so status timestamps follow creation time."""
    return 4 + (booking.pk or 0) % 40
