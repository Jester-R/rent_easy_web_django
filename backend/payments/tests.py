from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import PlatformSettings
from bookings.models import Booking, BookingStatus
from listings.models import Property
from notifications.models import Notification
from payments.gateways import aba
from payments.gateways import stripe as stripe_gateway
from payments.models import Payment, Refund
from payments.services import (
    RefundRequiresGateway,
    UnsupportedPaymentMethod,
    apply_aba_callback,
    apply_stripe_event,
    confirm_aba_payment,
    confirm_stripe_payment,
    normalize_method,
    pay_booking,
    process_refund,
)

User = get_user_model()

ABA_SETTINGS = {
    "ABA_PAYWAY_MERCHANT_ID": "ec123456",
    "ABA_PAYWAY_API_KEY": "sandbox-secret",
    "ABA_PAYWAY_ENABLED": True,
    "ABA_PAYWAY_BASE_URL": "https://checkout-sandbox.payway.com.kh",
    "ABA_PAYWAY_CALLBACK_URL": "https://example.test/payments/aba/callback/",
    "ABA_PAYWAY_RETURN_URL": "https://example.test/payments/aba/return/?payment={payment_id}",
    "ABA_PAYWAY_CANCEL_URL": "https://example.test/bookings",
    "ABA_PAYWAY_CURRENCY": "USD",
    "ABA_PAYWAY_LIFETIME_MINUTES": 30,
}

# Kept as a literal (not derived from the client) so a reordering regression is
# caught rather than silently mirrored by the test helper.
DOCUMENTED_PURCHASE_ORDER = (
    "req_time",
    "merchant_id",
    "tran_id",
    "amount",
    "items",
    "shipping",
    "firstname",
    "lastname",
    "email",
    "phone",
    "type",
    "payment_option",
    "return_url",
    "cancel_url",
    "continue_success_url",
    "return_deeplink",
    "currency",
    "custom_fields",
    "return_params",
    "payout",
    "lifetime",
    "additional_params",
    "google_pay_token",
    "skip_success_page",
)


def _manual_signature(fields: dict, order: tuple[str, ...], key: str) -> str:
    joined = "".join(str(fields.get(name, "") or "") for name in order)
    digest = hmac.new(key.encode(), joined.encode(), hashlib.sha512).digest()
    return base64.b64encode(digest).decode()


def _callback_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".14g")
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":")).replace("/", "\\/")


@override_settings(**ABA_SETTINGS)
class PayWaySignatureTests(TestCase):
    def test_purchase_hash_uses_documented_order(self):
        fields = {name: "" for name in aba.PURCHASE_HASH_FIELDS}
        fields.update(
            {
                "req_time": "20261026120000",
                "merchant_id": "ec123456",
                "tran_id": "PAY-ABCDEF123456",
                "amount": "100",
                "currency": "USD",
                "type": "purchase",
                "lifetime": "30",
                "skip_success_page": "1",
            }
        )
        self.assertEqual(
            aba.hash_fields(fields),
            _manual_signature(fields, DOCUMENTED_PURCHASE_ORDER, "sandbox-secret"),
        )
        self.assertEqual(aba.PURCHASE_HASH_FIELDS, DOCUMENTED_PURCHASE_ORDER)
        self.assertEqual(aba.CHECK_HASH_FIELDS, ("req_time", "merchant_id", "tran_id"))

    def test_callback_signature_round_trip(self):
        payload = {
            "tran_id": "PAY-ABCDEF123456",
            "status": "0",
            "total_amount": 100.0,
            "payment_amount": 100.0,
            "return_params": '{"payment_id": 7}',
        }
        raw = json.dumps(payload).encode()
        before_hash = "".join(_callback_value(payload[key]) for key in sorted(payload))
        signature = base64.b64encode(
            hmac.new(b"sandbox-secret", before_hash.encode(), hashlib.sha512).digest()
        ).decode()

        self.assertTrue(aba.verify_callback_signature(raw, signature))
        self.assertFalse(aba.verify_callback_signature(raw, "not-a-signature"))

    def test_purchase_form_omits_unset_callback_and_resolves_payment_id(self):
        checkout = aba.create_purchase_form(
            tran_id="PAY-ABCDEF123456",
            amount="100.00",
            return_params='{"payment_id": 7}',
        )
        fields = checkout["fields"]
        self.assertEqual(
            fields["continue_success_url"],
            "https://example.test/payments/aba/return/?payment=7",
        )
        self.assertIn("return_url", fields)

        with override_settings(**{**ABA_SETTINGS, "ABA_PAYWAY_CALLBACK_URL": ""}):
            checkout = aba.create_purchase_form(
                tran_id="PAY-ABCDEF123456", amount="100.00"
            )
        self.assertNotIn("return_url", checkout["fields"])
        self.assertEqual(checkout["fields"]["amount"], "100")

    def test_amount_formatting(self):
        self.assertEqual(aba.amount_to_string(Decimal("100.00")), "100")
        self.assertEqual(aba.amount_to_string(Decimal("0.10")), "0.1")
        self.assertEqual(aba.amount_to_string(Decimal("12.34")), "12.34")

    def test_callback_signature_requires_configured_gateway(self):
        payload = {"tran_id": "PAY-ABCDEF123456", "status": "0"}
        raw = json.dumps(payload).encode()
        before_hash = "".join(_callback_value(payload[key]) for key in sorted(payload))
        signature = base64.b64encode(
            hmac.new(b"sandbox-secret", before_hash.encode(), hashlib.sha512).digest()
        ).decode()

        with override_settings(**{**ABA_SETTINGS, "ABA_PAYWAY_ENABLED": False}):
            self.assertFalse(aba.verify_callback_signature(raw, signature))

    def test_callback_values_match_php_casting(self):
        self.assertEqual(aba._callback_value(100.0), "100")
        self.assertEqual(aba._callback_value(0.01), "0.01")
        self.assertEqual(aba._callback_value(100), "100")
        self.assertEqual(aba._callback_value(True), "1")
        self.assertEqual(aba._callback_value(False), "")
        self.assertEqual(aba._callback_value(None), "")


class PaymentMethodTests(TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_method("aba"), Payment.Method.ABA)
        self.assertEqual(normalize_method("ABA Pay"), Payment.Method.ABA)
        self.assertEqual(normalize_method("aba pay (mock)"), Payment.Method.ABA_MOCK)
        self.assertEqual(normalize_method("card"), Payment.Method.CARD)
        self.assertEqual(normalize_method(None), Payment.Method.ABA)


class AbaPaymentFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="owner@example.test", username="owner", password="x", role="owner"
        )
        cls.renter = User.objects.create_user(
            email="renter@example.test", username="renter", password="x", role="renter"
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Test Apartment",
            location="Phnom Penh",
            price_per_month=Decimal("100.00"),
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
            monthly_rent=Decimal("100.00"),
        )

    def _pending_payment(self, ref: str = "PAY-TEST00000001") -> Payment:
        return Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("100.00"),
            method=Payment.Method.ABA,
            status=Payment.Status.PENDING,
            provider=Payment.Provider.ABA_PAYWAY,
            provider_ref=ref,
        )

    @override_settings(**ABA_SETTINGS)
    def test_confirm_links_booking_and_notifies_once(self):
        payment = self._pending_payment()

        self.assertTrue(
            confirm_aba_payment(
                payment.pk, status="APPROVED", amount="100.00", payload={}
            )
        )
        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(self.booking.payment_id, payment.pk)
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)
        renter_notification = Notification.objects.get(
            recipient=self.renter, kind=Notification.Kind.PAYMENT_SUCCESS
        )
        self.assertEqual(renter_notification.title_key, "notif_payment_success")
        self.assertEqual(renter_notification.params["amount"], payment.amount_display)

        # Idempotent: a duplicate callback must not notify again.
        self.assertTrue(
            confirm_aba_payment(
                payment.pk, status="APPROVED", amount="100.00", payload={}
            )
        )
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.renter, kind=Notification.Kind.PAYMENT_SUCCESS
            ).count(),
            1,
        )

    @override_settings(**ABA_SETTINGS)
    def test_amount_mismatch_does_not_confirm(self):
        payment = self._pending_payment("PAY-TEST00000002")

        self.assertFalse(
            confirm_aba_payment(
                payment.pk, status="APPROVED", amount="99.00", payload={}
            )
        )
        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertIsNone(self.booking.payment_id)

    @override_settings(**ABA_SETTINGS)
    def test_booking_already_paid_is_rejected(self):
        first = self._pending_payment("PAY-TEST00000003")
        self.assertTrue(
            confirm_aba_payment(
                first.pk, status="APPROVED", amount="100.00", payload={}
            )
        )
        second = self._pending_payment("PAY-TEST00000004")

        self.assertFalse(
            confirm_aba_payment(
                second.pk, status="APPROVED", amount="100.00", payload={}
            )
        )
        second.refresh_from_db()
        self.assertEqual(second.status, Payment.Status.FAILED)
        self.assertEqual(second.refund_status, Payment.RefundStatus.PENDING)
        self.assertEqual(second.gateway_payload.get("error"), "booking_already_paid")
        # The renter was really charged, so the duplicate is queued for a
        # PayWay-portal refund instead of disappearing.
        duplicate_refund = Refund.objects.get(payment=second)
        self.assertEqual(duplicate_refund.status, Refund.Status.PENDING)
        self.assertEqual(duplicate_refund.reason, Refund.Reason.OTHER)

        # Recording the external PayWay refund must stay final even if PayWay
        # delivers the duplicate callback again.
        self.assertTrue(process_refund(duplicate_refund, external=True))
        self.assertFalse(
            confirm_aba_payment(
                second.pk, status="APPROVED", amount="100.00", payload={}
            )
        )
        second.refresh_from_db()
        self.assertEqual(second.refund_status, Payment.RefundStatus.PROCESSED)
        self.assertEqual(Refund.objects.filter(payment=second).count(), 1)

    @override_settings(**ABA_SETTINGS)
    def test_callback_matches_payment_by_tran_id(self):
        payment = self._pending_payment("PAY-TEST00000005")
        payload = {
            "tran_id": payment.provider_ref,
            "status": "0",
            "total_amount": 100.0,
            "payment_amount": 100.0,
            "return_params": json.dumps({"payment_id": payment.pk}),
        }
        check_data = {
            "payment_status": "APPROVED",
            "payment_amount": 100.0,
            "total_amount": 100.0,
        }
        with patch.object(aba, "check_transaction", return_value=check_data):
            self.assertTrue(apply_aba_callback(payload))

        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.booking.payment_id, payment.pk)

    @override_settings(**ABA_SETTINGS)
    def test_callback_verifies_original_amount_not_payer_currency(self):
        payment = self._pending_payment("PAY-TEST00000011")
        payload = {
            "tran_id": payment.provider_ref,
            "status": "0",
            "original_amount": 100.0,
            "total_amount": 100.0,
            # Payer settled in KHR; this must not be compared to the USD amount.
            "payment_amount": 410000.0,
            "payment_currency": "KHR",
            "return_params": json.dumps({"payment_id": payment.pk}),
        }
        check_data = {
            "payment_status": "APPROVED",
            "original_amount": 100.0,
            "total_amount": 100.0,
            "payment_amount": 410000.0,
            "payment_currency": "KHR",
        }
        with patch.object(aba, "check_transaction", return_value=check_data):
            self.assertTrue(apply_aba_callback(payload))

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

    @override_settings(**ABA_SETTINGS)
    def test_callback_for_wrong_payment_id_is_rejected(self):
        payment = self._pending_payment("PAY-TEST00000006")
        payload = {
            "tran_id": payment.provider_ref,
            "status": "0",
            "payment_amount": 100.0,
            "total_amount": 100.0,
            "return_params": json.dumps({"payment_id": payment.pk + 1}),
        }
        with patch.object(
            aba, "check_transaction", return_value={"payment_status": "APPROVED"}
        ):
            self.assertFalse(apply_aba_callback(payload))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @override_settings(**ABA_SETTINGS)
    def test_pay_booking_starts_pending_qr(self):
        qr = {
            "image": "data:image/png;base64,qr",
            "qr_string": "000201010212",
            "deeplink": "",
            "amount": "100",
            "currency": "USD",
            "expires_in": 30,
        }
        with patch.object(aba, "create_qr_payment", return_value=qr) as create:
            result = pay_booking(booking=self.booking, method="ABA Pay")

        self.assertEqual(result.payment.status, Payment.Status.PENDING)
        self.assertEqual(result.payment.provider, Payment.Provider.ABA_PAYWAY)
        self.assertEqual(result.qr, qr)
        self.assertIsNone(result.checkout)
        self.assertEqual(result.payment.provider_ref, result.payment.reference)
        create.assert_called_once()

    @override_settings(**ABA_SETTINGS)
    def test_simulated_success_cannot_bypass_configured_gateway(self):
        qr = {
            "image": "data:image/png;base64,qr",
            "qr_string": "000201010212",
            "deeplink": "",
            "amount": "100",
            "currency": "USD",
            "expires_in": 30,
        }
        with patch.object(aba, "create_qr_payment", return_value=qr):
            result = pay_booking(
                booking=self.booking, method="ABA Pay", simulate="success"
            )

        self.assertEqual(result.payment.status, Payment.Status.PENDING)
        self.assertEqual(result.payment.provider, Payment.Provider.ABA_PAYWAY)
        self.assertEqual(result.qr, qr)

    @override_settings(**{**ABA_SETTINGS, "ABA_PAYWAY_ENABLED": False})
    def test_without_credentials_requires_gateway_configuration(self):
        with self.assertRaises(aba.PayWayError) as raised:
            pay_booking(booking=self.booking, method="ABA Pay", simulate="success")
        self.assertEqual(raised.exception.code, "not_configured")

    @override_settings(**ABA_SETTINGS)
    def test_callback_without_amount_stays_pending_when_check_fails(self):
        payment = self._pending_payment("PAY-TEST00000009")
        payload = {
            "tran_id": payment.provider_ref,
            "status": "0",
            "return_params": json.dumps({"payment_id": payment.pk}),
        }
        with patch.object(
            aba, "check_transaction", side_effect=aba.PayWayError("6", "not found")
        ):
            self.assertFalse(apply_aba_callback(payload))

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def _refund_for(self, payment: Payment) -> Refund:
        refund = Refund.objects.create(
            payment=payment,
            booking=self.booking,
            amount=payment.amount,
            reason=Refund.Reason.CANCELLED_BY_RENTER,
        )
        payment.refund_status = Payment.RefundStatus.PENDING
        payment.save(update_fields=["refund_status"])
        return refund

    def test_real_payway_refund_requires_gateway(self):
        payment = self._pending_payment("PAY-TEST00000008")
        payment.status = Payment.Status.SUCCESS
        payment.save(update_fields=["status"])
        refund = self._refund_for(payment)

        with self.assertRaises(RefundRequiresGateway):
            process_refund(refund)

        refund.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PENDING)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PENDING)
        self.assertEqual(payment.refunded_amount, Decimal("0.00"))

    def test_external_payway_refund_can_be_recorded(self):
        payment = self._pending_payment("PAY-TEST00000010")
        payment.status = Payment.Status.SUCCESS
        payment.save(update_fields=["status"])
        refund = self._refund_for(payment)

        self.assertTrue(process_refund(refund, external=True))
        # A second request must not refund twice or notify the renter twice.
        self.assertFalse(process_refund(refund, external=True))

        refund.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)
        self.assertIn("ABA PayWay", refund.note)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PROCESSED)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.renter,
                kind=Notification.Kind.REFUND_PROCESSED,
            ).count(),
            1,
        )

    def test_mock_payment_can_still_refund_locally(self):
        payment = Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("100.00"),
            method=Payment.Method.ABA_MOCK,
            status=Payment.Status.SUCCESS,
            provider=Payment.Provider.MOCK,
        )
        refund = self._refund_for(payment)

        self.assertTrue(process_refund(refund))

        refund.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PROCESSED)
        self.assertEqual(payment.refunded_amount, Decimal("100.00"))


STRIPE_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_sandbox-secret",
    "STRIPE_WEBHOOK_SECRET": "whsec_sandbox-secret",
    "STRIPE_ENABLED": True,
    "STRIPE_CURRENCY": "usd",
    "STRIPE_SESSION_MINUTES": 30,
    "STRIPE_RETURN_URL": "https://example.test/payments/stripe/return/?payment={payment_id}",
    "STRIPE_CANCEL_URL": "https://example.test/bookings",
}


def _signed_webhook(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header value for ``payload``."""
    issued = int(time.time()) if timestamp is None else timestamp
    signed = f"{issued}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={issued},v1={digest}"


def _session_event(session: dict, event_type: str):
    """Build a minimal Stripe event object shaped like the SDK's."""
    return SimpleNamespace(
        type=event_type,
        data=SimpleNamespace(object=SimpleNamespace(**session)),
    )


class _StripeObjectLike:
    """Mimic stripe-python 16 ``StripeObject``: not iterable, only ``to_dict``."""

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)

    def __iter__(self):
        raise TypeError("StripeObject is not iterable or a mapping")


class StripeObjectCompatTests(TestCase):
    def test_plain_dict_unwraps_stripe_objects(self):
        self.assertEqual(stripe_gateway.plain_dict(None), {})
        self.assertEqual(stripe_gateway.plain_dict({"a": "b"}), {"a": "b"})
        self.assertEqual(
            stripe_gateway.plain_dict(_StripeObjectLike({"a": "b"})), {"a": "b"}
        )

    @override_settings(**STRIPE_SETTINGS)
    def test_retrieve_checkout_session_handles_stripe_object_metadata(self):
        session = SimpleNamespace(
            id="cs_test_1",
            status="complete",
            payment_status="paid",
            amount_total=10000,
            currency="usd",
            payment_intent="pi_test_1",
            client_reference_id="PAY-TEST00000001",
            metadata=_StripeObjectLike({"payment_id": "8"}),
        )
        sessions = SimpleNamespace(retrieve=lambda session_id: session)
        client = SimpleNamespace(
            v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessions))
        )

        with patch.object(stripe_gateway, "_client", return_value=client):
            data = stripe_gateway.retrieve_checkout_session("cs_test_1")

        self.assertEqual(data["metadata"], {"payment_id": "8"})
        self.assertEqual(data["payment_status"], "paid")
        self.assertEqual(data["amount_total"], 10000)


class StripeGatewayTests(TestCase):
    def test_amount_uses_minor_units(self):
        self.assertEqual(stripe_gateway.amount_to_minor_units(Decimal("100.00")), 10000)
        self.assertEqual(stripe_gateway.amount_to_minor_units("12.34"), 1234)
        self.assertEqual(stripe_gateway.amount_to_minor_units(1), 100)
        with self.assertRaises(stripe_gateway.StripeGatewayError):
            stripe_gateway.amount_to_minor_units("not-a-number")

    def test_is_configured_requires_secret_key(self):
        with override_settings(**STRIPE_SETTINGS):
            self.assertTrue(stripe_gateway.is_configured())
        with override_settings(**{**STRIPE_SETTINGS, "STRIPE_ENABLED": False}):
            self.assertFalse(stripe_gateway.is_configured())
        with override_settings(**{**STRIPE_SETTINGS, "STRIPE_SECRET_KEY": ""}):
            self.assertFalse(stripe_gateway.is_configured())

    def test_platform_settings_override_environment(self):
        PlatformSettings.objects.create(
            pk=1,
            stripe_publishable_key="pk_admin",
            stripe_secret_key="sk_admin",
            stripe_webhook_secret="whsec_admin",
        )
        with override_settings(
            **{
                **STRIPE_SETTINGS,
                "STRIPE_ENABLED": False,
                "STRIPE_SECRET_KEY": "",
                "STRIPE_PUBLISHABLE_KEY": "",
                "STRIPE_WEBHOOK_SECRET": "",
            }
        ):
            self.assertTrue(stripe_gateway.is_configured())
            self.assertEqual(stripe_gateway.secret_key(), "sk_admin")
            self.assertEqual(stripe_gateway.publishable_key(), "pk_admin")
            self.assertEqual(stripe_gateway.webhook_secret(), "whsec_admin")

    def test_platform_webhook_secret_is_used_for_verification(self):
        PlatformSettings.objects.create(
            pk=1,
            stripe_secret_key="sk_admin",
            stripe_webhook_secret="whsec_admin",
        )
        payload = json.dumps(
            {"type": "checkout.session.completed", "data": {"object": {}}}
        ).encode()
        header = _signed_webhook(payload, "whsec_admin")
        with override_settings(
            **{
                **STRIPE_SETTINGS,
                "STRIPE_ENABLED": False,
                "STRIPE_SECRET_KEY": "",
                "STRIPE_WEBHOOK_SECRET": "whsec_env",
            }
        ):
            self.assertIsNotNone(
                stripe_gateway.construct_webhook_event(payload, header)
            )

    def test_webhook_signature_round_trip(self):
        payload = json.dumps(
            {"type": "checkout.session.completed", "data": {"object": {}}}
        ).encode()
        header = _signed_webhook(payload, "whsec_sandbox-secret")

        with override_settings(**STRIPE_SETTINGS):
            event = stripe_gateway.construct_webhook_event(payload, header)
            self.assertIsNotNone(event)
            self.assertEqual(event.type, "checkout.session.completed")
            self.assertIsNone(
                stripe_gateway.construct_webhook_event(payload, "t=1,v1=bad")
            )
            # A stale timestamp is outside the default tolerance.
            stale = _signed_webhook(payload, "whsec_sandbox-secret", timestamp=0)
            self.assertIsNone(stripe_gateway.construct_webhook_event(payload, stale))
            # A signature signed with a different secret must be rejected.
            other = _signed_webhook(payload, "whsec_other-secret")
            self.assertIsNone(stripe_gateway.construct_webhook_event(payload, other))

    def test_webhook_requires_configuration(self):
        payload = json.dumps({"type": "checkout.session.completed"}).encode()
        header = _signed_webhook(payload, "whsec_sandbox-secret")
        with override_settings(**{**STRIPE_SETTINGS, "STRIPE_ENABLED": False}):
            self.assertIsNone(
                stripe_gateway.construct_webhook_event(payload, header)
            )


class StripePaymentFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="owner@example.test", username="owner2", password="x", role="owner"
        )
        cls.renter = User.objects.create_user(
            email="renter@example.test", username="renter2", password="x", role="renter"
        )
        cls.property = Property.objects.create(
            owner=cls.owner,
            title="Test Apartment 2",
            location="Phnom Penh",
            price_per_month=Decimal("100.00"),
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
            monthly_rent=Decimal("100.00"),
        )

    def _pending_payment(self, session_id: str = "cs_test_00000001") -> Payment:
        return Payment.objects.create(
            property=self.property,
            user=self.renter,
            booking=self.booking,
            amount=Decimal("100.00"),
            method=Payment.Method.STRIPE,
            status=Payment.Status.PENDING,
            provider=Payment.Provider.STRIPE,
            provider_ref=session_id,
        )

    def _paid_session(self, payment: Payment, session_id: str | None = None):
        session_id = session_id or payment.provider_ref
        return {
            "id": session_id,
            "status": "complete",
            "payment_status": "paid",
            "amount_total": stripe_gateway.amount_to_minor_units(payment.amount),
            "currency": "usd",
            "payment_intent": "pi_test_00000001",
            "client_reference_id": payment.reference,
            "metadata": {"payment_id": str(payment.pk)},
        }

    def test_aliases(self):
        self.assertEqual(normalize_method("stripe"), Payment.Method.STRIPE)
        self.assertEqual(normalize_method("Stripe Card"), Payment.Method.STRIPE)
        self.assertEqual(normalize_method("STRIPE CHECKOUT"), Payment.Method.STRIPE)
        with self.assertRaises(UnsupportedPaymentMethod):
            normalize_method("crypto")

    @override_settings(**STRIPE_SETTINGS)
    def test_pay_booking_starts_pending_checkout(self):
        session = {
            "provider": "stripe",
            "id": "cs_test_00000002",
            "url": "https://checkout.stripe.com/c/pay/cs_test_00000002",
            "expires_at": 1800000000,
            "amount_total": 10000,
            "currency": "usd",
        }
        with patch.object(
            stripe_gateway, "create_checkout_session", return_value=session
        ) as create:
            result = pay_booking(booking=self.booking, method="Stripe Card")

        self.assertEqual(result.payment.status, Payment.Status.PENDING)
        self.assertEqual(result.payment.provider, Payment.Provider.STRIPE)
        self.assertEqual(result.payment.method, Payment.Method.STRIPE)
        self.assertEqual(result.payment.provider_ref, session["id"])
        self.assertEqual(
            result.checkout, {"provider": "stripe", "url": session["url"]}
        )
        create.assert_called_once()
        create_kwargs = create.call_args.kwargs
        self.assertEqual(create_kwargs["payment_id"], result.payment.pk)
        self.assertEqual(create_kwargs["client_reference_id"], result.payment.reference)

    @override_settings(**{**STRIPE_SETTINGS, "STRIPE_ENABLED": False})
    def test_pay_booking_requires_configuration(self):
        with self.assertRaises(stripe_gateway.StripeGatewayError):
            pay_booking(booking=self.booking, method="Stripe Card")
        # Nothing was charged and no payment row is left behind.
        self.assertEqual(Payment.objects.filter(user=self.renter).count(), 0)

    @override_settings(**STRIPE_SETTINGS)
    def test_confirm_links_booking_and_notifies_once(self):
        payment = self._pending_payment()
        session = self._paid_session(payment)

        self.assertTrue(
            confirm_stripe_payment(payment.pk, session=session, payload={})
        )
        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(self.booking.payment_id, payment.pk)
        self.assertEqual(
            payment.gateway_payload["stripe"]["payment_intent"], "pi_test_00000001"
        )
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)

        # Idempotent: a duplicate webhook must not notify again.
        self.assertTrue(
            confirm_stripe_payment(payment.pk, session=session, payload={})
        )
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)

    @override_settings(**STRIPE_SETTINGS)
    def test_open_unpaid_session_stays_pending(self):
        payment = self._pending_payment("cs_test_00000003")
        session = {
            **self._paid_session(payment),
            "status": "open",
            "payment_status": "unpaid",
        }

        self.assertFalse(
            confirm_stripe_payment(payment.pk, session=session, payload={})
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @override_settings(**STRIPE_SETTINGS)
    def test_expired_session_fails_payment(self):
        payment = self._pending_payment("cs_test_00000004")
        session = {
            **self._paid_session(payment),
            "status": "expired",
            "payment_status": "unpaid",
        }

        self.assertFalse(
            confirm_stripe_payment(payment.pk, session=session, payload={})
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.gateway_payload.get("error"), "session_expired")

    @override_settings(**STRIPE_SETTINGS)
    def test_amount_mismatch_does_not_confirm(self):
        payment = self._pending_payment("cs_test_00000005")
        session = {**self._paid_session(payment), "amount_total": 9900}

        self.assertFalse(
            confirm_stripe_payment(payment.pk, session=session, payload={})
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.gateway_payload.get("error"), "amount_mismatch")
        self.assertIsNone(self.booking.payment_id)

    @override_settings(**STRIPE_SETTINGS)
    def test_duplicate_payment_for_paid_booking_queues_refund(self):
        first = self._pending_payment("cs_test_00000006")
        self.assertTrue(
            confirm_stripe_payment(
                first.pk, session=self._paid_session(first), payload={}
            )
        )
        second = self._pending_payment("cs_test_00000007")
        second.booking = self.booking
        second.save()

        self.assertFalse(
            confirm_stripe_payment(
                second.pk, session=self._paid_session(second), payload={}
            )
        )
        second.refresh_from_db()
        self.assertEqual(second.status, Payment.Status.FAILED)
        self.assertEqual(second.refund_status, Payment.RefundStatus.PENDING)
        duplicate_refund = Refund.objects.get(payment=second)
        self.assertEqual(duplicate_refund.status, Refund.Status.PENDING)

    @override_settings(**STRIPE_SETTINGS)
    def test_webhook_event_confirms_payment(self):
        payment = self._pending_payment("cs_test_00000008")
        event = _session_event(self._paid_session(payment), "checkout.session.completed")

        self.assertTrue(apply_stripe_event(event))
        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.booking.payment_id, payment.pk)

    @override_settings(**STRIPE_SETTINGS)
    def test_webhook_event_with_stripe_object_metadata(self):
        payment = self._pending_payment("cs_test_00000012")
        obj = SimpleNamespace(**self._paid_session(payment))
        obj.metadata = _StripeObjectLike({"payment_id": str(payment.pk)})
        event = SimpleNamespace(
            type="checkout.session.completed", data=SimpleNamespace(object=obj)
        )

        self.assertTrue(apply_stripe_event(event))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

    @override_settings(**STRIPE_SETTINGS)
    def test_webhook_failed_event_fails_pending_payment(self):
        payment = self._pending_payment("cs_test_00000009")
        session = {
            **self._paid_session(payment),
            "status": "expired",
            "payment_status": "unpaid",
        }
        event = _session_event(session, "checkout.session.expired")

        self.assertFalse(apply_stripe_event(event))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    @override_settings(**STRIPE_SETTINGS)
    def test_webhook_ignores_unrelated_events_and_sessions(self):
        payment = self._pending_payment("cs_test_00000010")
        self.assertFalse(
            apply_stripe_event(SimpleNamespace(type="payment_intent.created", data=None))
        )

        # An event whose metadata points at this row but was signed for another
        # session must not confirm it.
        session = {
            **self._paid_session(payment, session_id="cs_test_other"),
            "status": "complete",
        }
        session["metadata"] = {"payment_id": str(payment.pk)}
        event = _session_event(session, "checkout.session.completed")
        self.assertFalse(apply_stripe_event(event))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @override_settings(**STRIPE_SETTINGS)
    def test_stripe_refund_uses_gateway_and_is_final(self):
        payment = self._pending_payment("cs_test_00000011")
        self.assertTrue(
            confirm_stripe_payment(
                payment.pk, session=self._paid_session(payment), payload={}
            )
        )
        refund = Refund.objects.create(
            payment=payment,
            booking=self.booking,
            amount=payment.amount,
            reason=Refund.Reason.CANCELLED_BY_RENTER,
        )
        payment.refund_status = Payment.RefundStatus.PENDING
        payment.save(update_fields=["refund_status"])

        gateway_refund = {"id": "re_test_00000001", "status": "succeeded", "amount": 10000}
        with patch.object(
            stripe_gateway, "create_refund", return_value=gateway_refund
        ) as create_refund_mock:
            self.assertTrue(process_refund(refund))
            create_refund_mock.assert_called_once()
            self.assertEqual(
                create_refund_mock.call_args.kwargs["payment_intent"],
                "pi_test_00000001",
            )
            self.assertEqual(
                create_refund_mock.call_args.kwargs["amount"], Decimal("100.00")
            )

        refund.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.PROCESSED)
        self.assertIn("Stripe", refund.note)
        self.assertEqual(payment.refund_status, Payment.RefundStatus.PROCESSED)
        self.assertEqual(payment.refunded_amount, Decimal("100.00"))

        # A second request must not refund twice or notify the renter twice.
        self.assertFalse(process_refund(refund))
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.renter,
                kind=Notification.Kind.REFUND_PROCESSED,
            ).count(),
            1,
        )
