from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking, BookingStatus
from listings.models import Property
from notifications.models import Notification
from payments.models import Payment, Payout, Refund
from payments.services import (
    PayoutBlocked,
    PayoutDetailsMissing,
    PayoutNotDue,
    cancel_payout_for_payment,
    create_payout_for_payment,
    pay_out,
    process_refund,
    release_due_payouts,
    transition_booking,
)

User = get_user_model()


class PayoutFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="owner@example.test",
            username="owner",
            password="x",
            role="owner",
            payout_method="aba",
            payout_account_name="Owner Name",
            payout_account_number="000123456",
            payout_bank_name="ABA Bank",
            payout_phone="012345678",
        )
        cls.renter = User.objects.create_user(
            email="renter@example.test", username="renter", password="x", role="renter"
        )
        cls.admin = User.objects.create_user(
            email="admin@example.test",
            username="admin",
            password="x",
            role="superadmin",
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Payout Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("250.00"),
            bedrooms=1,
            bathrooms=1,
            description="Test",
            category="apartment",
        )
        cls.booking = Booking.objects.create(
            property=cls.property,
            renter=cls.renter,
            owner=cls.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=Decimal("250.00"),
        )

    def _payment(self, *, status=Payment.Status.SUCCESS, paid_at=None) -> Payment:
        payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("250.00"),
            method=Payment.Method.ABA_MOCK,
            status=status,
            provider=Payment.Provider.MOCK,
            paid_at=paid_at or timezone.now(),
        )
        self.booking.payment = payment
        self.booking.save(update_fields=["payment"])
        return payment

    def _eligible_payout(self) -> Payout:
        payment = self._payment()
        payout = create_payout_for_payment(payment)
        payout.available_at = timezone.now() - timedelta(seconds=1)
        payout.save(update_fields=["available_at"])
        release_due_payouts()
        payout.refresh_from_db()
        return payout

    def test_successful_payment_schedules_payout_for_hold_period(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)

        self.assertIsNotNone(payout)
        self.assertEqual(payout.status, Payout.Status.SCHEDULED)
        self.assertEqual(payout.amount, Decimal("250.00"))
        self.assertEqual(payout.owner, self.owner)
        self.assertEqual(payout.payout_account_number, "000123456")
        self.assertAlmostEqual(
            payout.available_at,
            payment.paid_at + timedelta(days=7),
            delta=timedelta(seconds=2),
        )

    def test_payout_creation_is_idempotent(self):
        payment = self._payment()
        first = create_payout_for_payment(payment)
        second = create_payout_for_payment(payment)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payout.objects.filter(payment=payment).count(), 1)

    def test_due_payout_becomes_eligible(self):
        payout = self._eligible_payout()
        self.assertEqual(payout.status, Payout.Status.ELIGIBLE)
        self.assertTrue(payout.can_pay)

    def test_cannot_pay_before_hold_ends(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)

        with self.assertRaises(PayoutNotDue):
            pay_out(payout, actor=self.admin, note="too early")

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.SCHEDULED)

    def test_pay_out_requires_owner_payout_details(self):
        payout = self._eligible_payout()
        self.owner.payout_method = ""
        self.owner.payout_account_name = ""
        self.owner.payout_account_number = ""
        self.owner.save(
            update_fields=[
                "payout_method",
                "payout_account_name",
                "payout_account_number",
            ]
        )

        with self.assertRaises(PayoutDetailsMissing):
            pay_out(payout, actor=self.admin)

    def test_pay_out_records_transfer_and_notifies_owner(self):
        payout = self._eligible_payout()

        self.assertTrue(
            pay_out(payout, actor=self.admin, note="ABA transfer ref 12345")
        )

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PAID)
        self.assertEqual(payout.recorded_by, self.admin)
        self.assertEqual(payout.note, "ABA transfer ref 12345")
        self.assertIsNotNone(payout.paid_at)
        self.assertEqual(payout.payout_account_number, "000123456")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                kind=Notification.Kind.PAYOUT_PAID,
            ).exists()
        )
        self.assertFalse(pay_out(payout, actor=self.admin))

    def test_cancelling_inside_hold_cancels_payout_and_queues_refund(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)

        ok, code = transition_booking(
            self.booking, BookingStatus.CANCELLED, actor=self.renter
        )

        self.assertTrue(ok, code)
        payout.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.CANCELLED)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PENDING)
        self.assertTrue(
            Refund.objects.filter(
                payment=payment, status=Refund.Status.PENDING
            ).exists()
        )

    def test_cancelling_after_hold_is_blocked(self):
        self._eligible_payout()
        self.booking.refresh_from_db()

        ok, code = transition_booking(
            self.booking, BookingStatus.CANCELLED, actor=self.renter
        )

        self.assertFalse(ok)
        self.assertEqual(code, "payout_released")

    def test_owner_can_cancel_inside_hold(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)
        self.booking.refresh_from_db()

        ok, code = transition_booking(
            self.booking, BookingStatus.CANCELLED, actor=self.owner
        )

        self.assertTrue(ok, code)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.CANCELLED)
        self.assertTrue(
            Refund.objects.filter(
                payment=payment, reason=Refund.Reason.CANCELLED_BY_OWNER
            ).exists()
        )

    def test_processed_refund_cancels_payout(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)
        refund = Refund.objects.create(
            payment=payment,
            booking=self.booking,
            amount=payment.amount,
            reason=Refund.Reason.CANCELLED_BY_RENTER,
        )
        payment.refund_status = Payment.RefundStatus.PENDING
        payment.save(update_fields=["refund_status"])

        self.assertTrue(process_refund(refund, external=True))

        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.CANCELLED)

    def test_paid_out_payment_is_final(self):
        payout = self._eligible_payout()
        self.assertTrue(pay_out(payout, actor=self.admin))

        self.assertFalse(pay_out(payout, actor=self.admin))
        self.assertEqual(cancel_payout_for_payment(payout.payment), 0)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PAID)

    def test_refunded_payment_cannot_be_paid_out(self):
        payout = self._eligible_payout()
        payment = payout.payment
        payment.refund_status = Payment.RefundStatus.PROCESSED
        payment.save(update_fields=["refund_status"])

        with self.assertRaises(PayoutBlocked):
            pay_out(payout, actor=self.admin)

        # The failed attempt is rolled back; the list refresh then cancels it.
        release_due_payouts()
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.CANCELLED)
