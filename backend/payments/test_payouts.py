from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import PlatformSettings
from bookings.models import (
    Booking,
    BookingStatus,
    payment_window_hours,
    rebook_cooldown_hours,
)
from chat.models import Conversation
from core.bolt_serializers import booking as serialize_booking_data
from listings.models import (
    OwnerPropertyAction,
    Property,
    PropertyOwnerStatus,
    active_reservation_deadlines,
)
from listings.services import (
    OwnerActionBlocked,
    OwnerActionRateLimited,
    reopen_owner_property,
    set_owner_property_availability,
    soft_delete_owner_property,
)
from notifications.models import Notification
from payments.models import Payment, Payout, Refund, RefundMessage
from payments.services import (
    _attach_successful_payment,
    PayoutBlocked,
    RefundRequestError,
    accept_refund,
    add_refund_message,
    ensure_refund_chat,
    expire_unpaid_bookings,
    mark_refund_commission_paid,
    request_booking_cancellation,
    PayoutDetailsMissing,
    PayoutNotDue,
    cancel_payout_for_payment,
    create_booking,
    create_payout_for_payment,
    pay_out,
    process_refund,
    release_completed_bookings,
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

    def _payment(
        self, *, status=Payment.Status.SUCCESS, paid_at=None, gateway_payload=None
    ) -> Payment:
        payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("250.00"),
            method=Payment.Method.ABA_MOCK,
            status=status,
            provider=Payment.Provider.MOCK,
            paid_at=paid_at or timezone.now(),
            gateway_payload=gateway_payload or {},
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
            self.booking,
            BookingStatus.CANCELLED,
            actor=self.renter,
            request_note="Renter cannot travel",
        )

        self.assertTrue(ok, code)
        payout.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.CANCELLED)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PENDING)
        self.assertTrue(
            Refund.objects.filter(
                payment=payment,
                status=Refund.Status.PENDING,
                request_note="Renter cannot travel",
            ).exists()
        )

    def test_cancelling_after_seven_days_is_blocked(self):
        self._payment(paid_at=timezone.now() - timedelta(days=8))
        self.booking.refresh_from_db()

        ok, code = transition_booking(
            self.booking, BookingStatus.CANCELLED, actor=self.renter
        )

        self.assertFalse(ok)
        self.assertEqual(code, "cancellation_window_closed")

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

    def test_paid_booking_closes_listing_until_booking_is_no_longer_active(self):
        payment = self._payment()
        self.property.refresh_from_db()
        self.assertTrue(self.property.is_active)

        _attach_successful_payment(self.booking, payment)
        self.property.refresh_from_db()
        self.assertFalse(self.property.is_active)
        self.assertIsNotNone(self.property.rental_closed_at)
        self.assertEqual(self.property.owner_status, PropertyOwnerStatus.UNAVAILABLE)

        ok, code = transition_booking(
            self.booking, BookingStatus.CANCELLED, actor=self.renter
        )
        self.assertTrue(ok, code)
        self.property.refresh_from_db()
        self.assertTrue(self.property.is_active)
        self.assertIsNone(self.property.rental_closed_at)
        self.assertEqual(self.property.owner_status, PropertyOwnerStatus.AVAILABLE)

    def test_active_paid_property_is_hidden_from_renter_browse(self):
        other_renter = User.objects.create_user(
            email="other-renter@example.test",
            username="other-renter",
            password="x",
            role="renter",
        )
        self.assertIn(self.property, Property.objects.for_renter(other_renter))

        payment = self._payment()
        self.assertNotIn(self.property, Property.objects.for_renter(other_renter))

        Refund.objects.create(
            payment=payment,
            booking=self.booking,
            amount=payment.amount,
            reason=Refund.Reason.CANCELLED_BY_RENTER,
            status=Refund.Status.PROCESSED,
        )
        self.assertIn(self.property, Property.objects.for_renter(other_renter))

    def test_processed_refund_reopens_paid_property(self):
        payment = self._payment()
        _attach_successful_payment(self.booking, payment)
        self.property.refresh_from_db()
        self.assertFalse(self.property.is_active)

        refund = Refund.objects.create(
            payment=payment,
            booking=self.booking,
            amount=payment.amount,
            reason=Refund.Reason.CANCELLED_BY_RENTER,
            status=Refund.Status.ACCEPTED,
        )
        self.assertTrue(process_refund(refund, actor=self.admin))

        self.property.refresh_from_db()
        self.assertTrue(self.property.is_active)
        self.assertIsNone(self.property.rental_closed_at)
        self.assertEqual(self.property.owner_status, PropertyOwnerStatus.AVAILABLE)

    def test_owner_can_reopen_after_lease_end_date(self):
        payment = self._payment()
        _attach_successful_payment(self.booking, payment)
        self.booking.end_date = timezone.localdate() - timedelta(days=1)
        self.booking.save(update_fields=["end_date"])

        prop, ok = reopen_owner_property(self.property.pk, self.owner)

        self.assertTrue(ok)
        self.assertTrue(prop.is_active)
        self.assertIsNone(prop.rental_closed_at)

    def test_cancellation_request_holds_booking_for_admin_review(self):
        payment = self._payment()
        payout = create_payout_for_payment(payment)

        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Need to cancel"
        )

        self.assertEqual(code, "")
        self.assertIsNotNone(refund)
        self.assertEqual(refund.status, Refund.Status.PENDING)
        self.booking.refresh_from_db()
        payout.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.APPROVED)
        self.assertEqual(payout.status, Payout.Status.CANCELLED)
        self.assertTrue(
            Notification.objects.filter(kind=Notification.Kind.REFUND_REQUESTED).exists()
        )

    def test_six_day_cancellation_uses_admin_fee_not_payment_commission(self):
        PlatformSettings.objects.update_or_create(
            pk=1, defaults={"late_cancellation_fee": Decimal("12.50")}
        )
        self._payment(
            paid_at=timezone.now() - timedelta(days=6),
            gateway_payload={"commission": {"rate": "5.00", "amount": "99.00"}},
        )

        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Cancel after five days"
        )

        self.assertEqual(code, "")
        self.assertEqual(refund.commission_due, Decimal("12.50"))
        self.assertEqual(refund.commission_rate, Decimal("0.00"))
        with self.assertRaises(RefundRequestError) as error:
            accept_refund(refund, actor=self.admin)
        self.assertEqual(error.exception.code, "cancellation_fee_required")

        self.assertTrue(mark_refund_commission_paid(refund, actor=self.admin))
        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        refund.refresh_from_db()
        self.assertTrue(refund.commission_paid)
        self.assertEqual(refund.status, Refund.Status.ACCEPTED)

    def test_admin_accept_refunds_paid_booking_without_cancelling_it(self):
        payment = self._payment()
        _attach_successful_payment(self.booking, payment)
        self.property.refresh_from_db()
        self.assertFalse(self.property.is_active)

        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Cancel after payment"
        )
        self.assertEqual(code, "")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)

        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        self.booking.refresh_from_db()
        self.property.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)
        self.assertTrue(self.property.is_active)
        self.assertIsNone(self.property.rental_closed_at)

        self.assertTrue(process_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PROCESSED)
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)
        self.assertEqual(self.booking.refund_state, "Refunded")

    def test_refund_chats_are_one_to_one_and_created_after_acceptance(self):
        self._payment()
        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Need to discuss"
        )
        self.assertEqual(code, "")

        renter_message = add_refund_message(refund, self.renter, "Please refund me")
        with self.assertRaises(RefundRequestError) as blocked:
            add_refund_message(refund, self.admin, "We received your note")
        self.assertEqual(blocked.exception.code, "refund_not_accepted")
        self.assertFalse(Conversation.objects.filter(refund=refund).exists())
        with self.assertRaises(RefundRequestError) as blocked:
            ensure_refund_chat(refund, party="renter", admin=self.admin)
        self.assertEqual(blocked.exception.code, "refund_not_accepted")

        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        renter_chat = ensure_refund_chat(refund, party="renter", admin=self.admin)
        owner_chat = ensure_refund_chat(refund, party="owner", admin=self.admin)
        admin_message = add_refund_message(refund, self.admin, "We received your note")

        self.assertEqual(renter_message.refund_id, refund.pk)
        self.assertFalse(renter_message.is_from_admin)
        self.assertTrue(admin_message.is_from_admin)
        self.assertEqual(RefundMessage.objects.filter(refund=refund).count(), 2)
        self.assertEqual(Conversation.objects.filter(refund=refund).count(), 2)
        self.assertEqual(renter_chat.refund_party, "renter")
        self.assertEqual(renter_chat.refund_participant_id, self.renter.pk)
        self.assertEqual(renter_chat.support_admin_id, self.admin.pk)
        self.assertEqual(owner_chat.refund_party, "owner")
        self.assertEqual(owner_chat.refund_participant_id, self.owner.pk)
        self.assertNotEqual(renter_chat.pk, owner_chat.pk)
        self.assertTrue(
            Notification.objects.filter(kind=Notification.Kind.CHAT_MESSAGE).exists()
        )

        outsider = User.objects.create_user(
            email="outsider@example.test",
            username="outsider",
            password="x",
            role="renter",
        )
        with self.assertRaises(RefundRequestError) as error:
            add_refund_message(refund, outsider, "Let me in")
        self.assertEqual(error.exception.code, "not_authorized")

    def test_refund_chat_stays_open_after_processing(self):
        self._payment()
        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Need to discuss"
        )
        self.assertEqual(code, "")

        self.assertTrue(accept_refund(refund, actor=self.admin))
        refund.refresh_from_db()
        self.assertTrue(process_refund(refund, actor=self.admin))
        message = add_refund_message(refund, self.renter, "Thank you")

        self.assertEqual(message.refund_id, refund.pk)
        self.assertEqual(RefundMessage.objects.filter(refund=refund).count(), 1)

    def test_async_booking_serialization_loads_refund_state_without_prefetch(self):
        self._payment()
        refund, code = request_booking_cancellation(
            self.booking, self.renter, "Dashboard check"
        )
        self.assertEqual(code, "")
        self.assertIsNotNone(refund)

        data = async_to_sync(serialize_booking_data)(
            Booking.objects.get(pk=self.booking.pk)
        )

        self.assertEqual(data["refund_state"], "Refunding")

    def test_unpaid_renter_cancel_does_not_require_a_refund_request(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.PENDING,
            monthly_rent=Decimal("250.00"),
        )

        refund, code = request_booking_cancellation(
            booking, self.renter, "No longer needed"
        )

        self.assertEqual(code, "")
        self.assertIsNone(refund)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    def test_owner_cannot_cancel_unpaid_booking(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.PENDING,
            monthly_rent=Decimal("250.00"),
        )

        ok, code = transition_booking(
            booking, BookingStatus.CANCELLED, actor=self.owner
        )

        self.assertFalse(ok)
        self.assertEqual(code, "payment_required")

    def test_renter_can_cancel_unpaid_booking(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.PENDING,
            monthly_rent=Decimal("250.00"),
        )

        ok, code = transition_booking(
            booking, BookingStatus.CANCELLED, actor=self.renter
        )

        self.assertTrue(ok, code)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

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


class OwnerPropertyActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="action-owner@example.test",
            username="action-owner",
            password="x",
            role="owner",
        )
        cls.renter = User.objects.create_user(
            email="action-renter@example.test",
            username="action-renter",
            password="x",
            role="renter",
        )

    def _property(self, title: str) -> Property:
        return Property.objects.create(
            owner=self.owner,
            title=title,
            location="Phnom Penh",
            price_per_month=Decimal("250.00"),
            bedrooms=1,
            bathrooms=1,
            category="apartment",
        )

    def _paid_booking(self, prop: Property, *, paid_at) -> Booking:
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=Decimal("250.00"),
        )
        payment = Payment.objects.create(
            property=prop,
            user=self.renter,
            booking=booking,
            amount=Decimal("250.00"),
            method=Payment.Method.ABA_MOCK,
            status=Payment.Status.SUCCESS,
            provider=Payment.Provider.MOCK,
            paid_at=paid_at,
        )
        booking.payment = payment
        booking.save(update_fields=["payment"])
        return booking

    def test_owner_can_toggle_unavailable_without_deleting_data(self):
        prop = self._property("Toggle Apartment")

        prop, ok = set_owner_property_availability(prop.pk, self.owner, True)
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertFalse(prop.is_active)
        self.assertEqual(prop.owner_status, PropertyOwnerStatus.UNAVAILABLE)
        self.assertEqual(
            OwnerPropertyAction.objects.filter(action="unavailable").count(), 1
        )

        prop, ok = set_owner_property_availability(prop.pk, self.owner, False)
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertTrue(prop.is_active)
        self.assertEqual(prop.owner_status, PropertyOwnerStatus.AVAILABLE)
        self.assertEqual(OwnerPropertyAction.objects.count(), 1)

    def test_owner_hiding_property_rejects_unpaid_bookings(self):
        prop = self._property("Unpaid Apartment")
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.PENDING,
            monthly_rent=Decimal("250.00"),
        )

        prop, ok = set_owner_property_availability(prop.pk, self.owner, True)

        self.assertTrue(ok)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.REJECTED)
        self.assertIsNotNone(booking.rejected_at)

    def test_owner_hiding_property_cancels_pending_payment_and_rejects_booking(self):
        prop = self._property("Pending Payment Apartment")
        booking = Booking.objects.create(
            property=prop,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=Decimal("250.00"),
        )
        payment = Payment.objects.create(
            property=prop,
            user=self.renter,
            booking=booking,
            amount=Decimal("250.00"),
            method=Payment.Method.ABA_MOCK,
            status=Payment.Status.PENDING,
            provider=Payment.Provider.MOCK,
        )
        booking.payment = payment
        booking.save(update_fields=["payment"])

        set_owner_property_availability(prop.pk, self.owner, True)

        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertIsNone(booking.payment_id)
        self.assertEqual(booking.status, BookingStatus.REJECTED)
        self.assertEqual(payment.status, Payment.Status.CANCELLED)

    def test_owner_can_mark_rented_listing_available_after_booking_is_cancelled(self):
        prop = self._property("Cancelled Paid")
        booking = self._paid_booking(prop, paid_at=timezone.now())
        _attach_successful_payment(booking, booking.payment)
        prop.refresh_from_db()
        self.assertFalse(prop.is_active)
        self.assertIsNotNone(prop.rental_closed_at)

        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status"])

        prop, ok = set_owner_property_availability(prop.pk, self.owner, False)
        self.assertTrue(ok)
        prop.refresh_from_db()
        self.assertTrue(prop.is_active)
        self.assertIsNone(prop.rental_closed_at)
        self.assertEqual(prop.owner_status, PropertyOwnerStatus.AVAILABLE)

    def test_owner_cannot_mark_available_with_active_paid_booking(self):
        prop = self._property("Active Paid")
        booking = self._paid_booking(prop, paid_at=timezone.now())
        _attach_successful_payment(booking, booking.payment)

        with self.assertRaises(OwnerActionBlocked):
            set_owner_property_availability(prop.pk, self.owner, False)

    def test_owner_hide_actions_are_rate_limited_to_five_per_hour(self):
        props = [self._property(f"Rate Limited {index}") for index in range(6)]

        for prop in props[:5]:
            _, ok = set_owner_property_availability(prop.pk, self.owner, True)
            self.assertTrue(ok)

        with self.assertRaises(OwnerActionRateLimited):
            set_owner_property_availability(props[5].pk, self.owner, True)
        self.assertEqual(OwnerPropertyAction.objects.count(), 5)

    def test_owner_removal_queues_refund_only_inside_seven_day_window(self):
        recent_property = self._property("Recent Paid")
        self._paid_booking(recent_property, paid_at=timezone.now() - timedelta(days=2))
        _, queued = soft_delete_owner_property(recent_property.pk, self.owner)
        self.assertEqual(queued, 1)

        old_property = self._property("Old Paid")
        self._paid_booking(old_property, paid_at=timezone.now() - timedelta(days=8))
        _, queued = soft_delete_owner_property(old_property.pk, self.owner)
        self.assertEqual(queued, 0)
        self.assertEqual(Refund.objects.filter(payment__property=old_property).count(), 0)


class UnpaidReservationAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="reservation-owner@example.test",
            username="reservation-owner",
            password="x",
            role="owner",
            payout_method="aba",
            payout_account_name="Owner Name",
            payout_account_number="000123456",
            payout_bank_name="ABA Bank",
            payout_phone="012345678",
        )
        cls.renter = User.objects.create_user(
            email="reservation-renter@example.test",
            username="reservation-renter",
            password="x",
            role="renter",
        )
        cls.other_renter = User.objects.create_user(
            email="reservation-other@example.test",
            username="reservation-other",
            password="x",
            role="renter",
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Reservation Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("250.00"),
            bedrooms=1,
            bathrooms=1,
            description="Test",
            category="apartment",
        )

    def _request(self, renter):
        return create_booking(property_obj=self.property, renter=renter)

    def test_unpaid_reservation_keeps_listing_visible_and_reports_deadline(self):
        booking = self._request(self.renter)
        self.assertIsNotNone(booking)

        self.assertIn(self.property, Property.objects.for_renter(self.other_renter))
        deadlines = active_reservation_deadlines([self.property.pk])
        self.assertEqual(
            deadlines.get(self.property.pk),
            booking.payment_deadline_at.isoformat(),
        )

    def test_reserved_listing_hidden_from_other_renter_dashboard(self):
        from accounts.api import renter_dashboard

        self.assertIsNotNone(self._request(self.renter))

        class Request:
            query = {}
            params = {}
            session = None
            headers = {}

        with patch(
            "accounts.api.renter_required",
            new=AsyncMock(return_value=self.other_renter),
        ):
            data = async_to_sync(renter_dashboard)(Request())

        self.assertNotIn("reserved", data)
        self.assertNotIn(self.property.pk, [p["id"] for p in data["featured"]])
        self.assertNotIn(self.property.pk, [p["id"] for p in data["suggested"]])

    def test_other_renter_cannot_book_while_reservation_is_active(self):
        self.assertIsNotNone(self._request(self.renter))
        self.assertIsNone(self._request(self.other_renter))

    def test_cancelled_booking_stays_visible_but_blocks_same_renter(self):
        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.CANCELLED)

        self.assertIn(self.property, Property.objects.for_renter(self.renter))
        self.assertIsNone(self._request(self.renter))
        self.assertIsNotNone(self._request(self.other_renter))

    def test_cancelled_booking_reports_wait_time_instead_of_already_booked(self):
        from listings.api import renter_browse, renter_detail

        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.CANCELLED)
        expected = (
            booking.created_at + timedelta(hours=rebook_cooldown_hours())
        ).isoformat()

        class Request:
            query = {"page": "1", "page_size": "25"}
            params = {"pk": str(self.property.pk)}
            session = None
            headers = {}

        with (
            patch("listings.api.get_user", new=AsyncMock(return_value=self.renter)),
            patch(
                "listings.api.renter_required",
                new=AsyncMock(return_value=self.renter),
            ),
        ):
            browse = async_to_sync(renter_browse)(Request())
            detail = async_to_sync(renter_detail)(Request())

        item = next(p for p in browse["properties"] if p["id"] == self.property.pk)
        self.assertFalse(item["has_active_booking"])
        self.assertEqual(item["booking_status"], BookingStatus.CANCELLED)
        self.assertEqual(item["rebook_available_at"], expected)

        self.assertFalse(detail["has_active_booking"])
        self.assertEqual(detail["booking_status"], BookingStatus.CANCELLED)
        self.assertEqual(detail["rebook_available_at"], expected)

    def test_same_renter_blocked_right_before_cooldown_expires(self):
        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(
            status=BookingStatus.CANCELLED,
            created_at=timezone.now()
            - timedelta(hours=rebook_cooldown_hours() - 1),
        )

        self.assertIsNone(self._request(self.renter))

    def test_same_renter_can_rebook_after_cooldown_expires(self):
        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(
            status=BookingStatus.CANCELLED,
            created_at=timezone.now()
            - timedelta(hours=rebook_cooldown_hours() + 1),
        )

        self.assertIsNotNone(self._request(self.renter))

    def test_available_filter_hides_unpaid_reservations(self):
        from listings.api import renter_browse

        self.assertIsNotNone(self._request(self.renter))

        class Request:
            query = {"availability": "available", "page": "1", "page_size": "25"}
            params = {}
            session = None
            headers = {}

        data = async_to_sync(renter_browse)(Request())
        self.assertNotIn(
            self.property.pk, [p["id"] for p in data["properties"]]
        )
        self.assertEqual(data["filters"]["availability"], "available")

    def test_available_filter_hides_cancelled_cooldown_for_same_renter(self):
        from listings.api import renter_browse

        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.CANCELLED)

        class Request:
            query = {"availability": "available", "page": "1", "page_size": "25"}
            params = {}
            session = None
            headers = {}

        with patch("listings.api.get_user", new=AsyncMock(return_value=self.renter)):
            data = async_to_sync(renter_browse)(Request())
        self.assertNotIn(self.property.pk, [p["id"] for p in data["properties"]])

        with patch(
            "listings.api.get_user", new=AsyncMock(return_value=self.other_renter)
        ):
            data = async_to_sync(renter_browse)(Request())
        self.assertIn(self.property.pk, [p["id"] for p in data["properties"]])

    def test_reservation_expires_after_payment_window(self):
        booking = self._request(self.renter)
        Booking.objects.filter(pk=booking.pk).update(
            created_at=timezone.now() - timedelta(hours=payment_window_hours() + 1)
        )

        self.assertGreaterEqual(expire_unpaid_bookings(), 1)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.EXPIRED)
        self.assertNotIn(
            self.property.pk, active_reservation_deadlines([self.property.pk])
        )
        self.assertIsNotNone(self._request(self.other_renter))

    def test_approved_unpaid_reservation_also_expires(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.APPROVED,
            monthly_rent=self.property.price_per_month,
        )
        Booking.objects.filter(pk=booking.pk).update(
            created_at=timezone.now() - timedelta(hours=payment_window_hours() + 1)
        )

        expire_unpaid_bookings()
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.EXPIRED)

    def test_owner_release_rejects_unpaid_reservation(self):
        booking = self._request(self.renter)
        self.assertIsNotNone(booking)

        _, ok = set_owner_property_availability(
            self.property.pk, self.owner, unavailable=False
        )
        self.assertTrue(ok)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.REJECTED)
        self.assertNotIn(
            self.property.pk, active_reservation_deadlines([self.property.pk])
        )
        self.assertIsNotNone(self._request(self.other_renter))

    def test_completed_paid_booking_reopens_listing_automatically(self):
        booking = Booking.objects.create(
            property=self.property,
            renter=self.renter,
            owner=self.owner,
            status=BookingStatus.PENDING,
            monthly_rent=self.property.price_per_month,
            move_in_date=timezone.localdate() - timedelta(days=60),
            end_date=timezone.localdate() - timedelta(days=1),
        )
        paid_at = timezone.now() - timedelta(days=60)
        payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=booking,
            amount=self.property.price_per_month,
            method=Payment.Method.ABA_MOCK,
            status=Payment.Status.SUCCESS,
            provider=Payment.Provider.MOCK,
            paid_at=paid_at,
            gateway_payload={},
        )
        _attach_successful_payment(booking, payment)
        self.property.refresh_from_db()
        self.assertFalse(self.property.is_active)
        self.assertNotIn(self.property, Property.objects.for_renter(self.other_renter))

        self.assertEqual(release_completed_bookings(), 1)
        self.property.refresh_from_db()
        self.assertTrue(self.property.is_active)
        self.assertIsNone(self.property.rental_closed_at)
        self.assertEqual(self.property.owner_status, PropertyOwnerStatus.AVAILABLE)
        self.assertIn(self.property, Property.objects.for_renter(self.other_renter))
        self.assertIsNotNone(self._request(self.other_renter))
