"""Stripe Checkout client (hosted Checkout, test mode supported).

Rent is collected on Stripe's hosted checkout page:

1. :func:`create_checkout_session` starts a ``payment``-mode session for the
   pending payment row; ``provider_ref`` stores the session id so later events
   can find the row without trusting client input.
2. Stripe POSTs ``checkout.session.*`` events to ``/payments/stripe/webhook/``;
   the payload is verified through :func:`construct_webhook_event` with
   ``STRIPE_WEBHOOK_SECRET``.
3. :func:`retrieve_checkout_session` is the authoritative reconciliation path
   used by the return/refresh endpoints (useful when the webhook cannot reach
   a local development server).

Test mode ("sandbox"): set ``STRIPE_SECRET_KEY`` to an ``sk_test_...`` key from
the Stripe Dashboard (Developers > API keys) and complete checkout with the
documented test cards, e.g. ``4242 4242 4242 4242``. No real money moves.

Docs: https://docs.stripe.com/payments/checkout
"""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings

#: Session events that carry a final payment outcome.
COMPLETED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
)
FAILED_EVENTS = frozenset(
    {
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }
)


class StripeGatewayError(RuntimeError):
    """A Stripe API call returned an error or was unreachable."""

    def __init__(self, code: str, message: str, payload: dict | None = None):
        self.code = str(code or "")
        self.message = message or "Stripe request failed"
        self.payload = payload or {}
        super().__init__(f"{self.code}: {self.message}" if self.code else self.message)


def is_configured() -> bool:
    """Whether real Stripe calls are enabled for this environment."""
    return bool(
        getattr(settings, "STRIPE_ENABLED", False)
        and getattr(settings, "STRIPE_SECRET_KEY", "")
    )


def amount_to_minor_units(value: Decimal | int | float | str) -> int:
    """Stripe amounts are integers in the currency's smallest unit (USD cents)."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StripeGatewayError("invalid_amount", f"Invalid amount: {value!r}") from exc
    return int((amount * Decimal("100")).quantize(Decimal("1")))


def plain_dict(value) -> dict:
    """Unwrap a Stripe SDK object into a plain ``dict``.

    Since stripe-python 16 ``StripeObject`` is no longer iterable or a mapping,
    so ``dict(metadata)`` raises ``TypeError``; ``to_dict()`` is the supported
    conversion.
    """
    if not value:
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _client():
    """Return a Stripe client bound to the configured secret key."""
    import stripe as stripe_sdk

    if not is_configured():
        raise StripeGatewayError("not_configured", "Stripe is not configured")
    return stripe_sdk.StripeClient(settings.STRIPE_SECRET_KEY)


def _call(operation):
    """Run a Stripe SDK call, translating SDK failures to gateway errors."""
    import stripe as stripe_sdk

    try:
        return operation()
    except stripe_sdk.StripeError as exc:
        code = getattr(exc, "code", "") or type(exc).__name__
        raise StripeGatewayError(str(code), str(exc)) from exc


def create_checkout_session(
    *,
    client_reference_id: str,
    amount: Decimal | int | float | str,
    description: str,
    email: str = "",
    payment_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a hosted Stripe Checkout session and return its URL."""
    if not is_configured():
        raise StripeGatewayError("not_configured", "Stripe is not configured")
    meta = {str(key): str(value) for key, value in (metadata or {}).items()}
    if payment_id is not None:
        meta["payment_id"] = str(payment_id)
    params: dict[str, Any] = {
        "mode": "payment",
        "client_reference_id": str(client_reference_id)[:64],
        "customer_email": email or None,
        "line_items": [
            {
                "quantity": 1,
                "price_data": {
                    "currency": settings.STRIPE_CURRENCY,
                    "unit_amount": amount_to_minor_units(amount),
                    "product_data": {"name": str(description)[:255] or "Rent payment"},
                },
            }
        ],
        "success_url": settings.STRIPE_RETURN_URL.format(
            payment_id=meta.get("payment_id", "")
        ),
        "cancel_url": settings.STRIPE_CANCEL_URL,
        "metadata": meta,
        "expires_at": int(time.time()) + int(settings.STRIPE_SESSION_MINUTES) * 60,
    }
    session = _call(
        lambda: _client().v1.checkout.sessions.create(
            {key: value for key, value in params.items() if value is not None}
        )
    )
    if not getattr(session, "url", ""):
        raise StripeGatewayError(
            "invalid_response", "Stripe response did not include a checkout URL"
        )
    return {
        "provider": "stripe",
        "id": session.id,
        "url": session.url,
        "expires_at": session.expires_at,
        "amount_total": session.amount_total,
        "currency": session.currency,
    }


def retrieve_checkout_session(session_id: str) -> dict[str, Any]:
    """Fetch the authoritative session status from Stripe."""
    if not is_configured():
        raise StripeGatewayError("not_configured", "Stripe is not configured")
    session = _call(lambda: _client().v1.checkout.sessions.retrieve(session_id))
    payment_intent = session.payment_intent
    if payment_intent is not None and not isinstance(payment_intent, str):
        payment_intent = getattr(payment_intent, "id", "") or ""
    return {
        "id": session.id,
        "status": session.status,
        "payment_status": session.payment_status,
        "amount_total": session.amount_total,
        "currency": session.currency,
        "payment_intent": payment_intent or "",
        "client_reference_id": session.client_reference_id or "",
        "metadata": plain_dict(session.metadata),
    }


def create_refund(*, payment_intent: str, amount: Decimal | int | float | str) -> dict[str, Any]:
    """Refund a PaymentIntent through Stripe's Refund API."""
    if not is_configured():
        raise StripeGatewayError("not_configured", "Stripe is not configured")
    refund = _call(
        lambda: _client().v1.refunds.create(
            {
                "payment_intent": payment_intent,
                "amount": amount_to_minor_units(amount),
            }
        )
    )
    return {"id": refund.id, "status": refund.status, "amount": refund.amount}


def construct_webhook_event(raw_body: bytes, signature: str):
    """Verify the ``Stripe-Signature`` header and return the parsed event.

    Returns ``None`` when the gateway is unconfigured or verification fails;
    callers must treat that as an untrusted payload.
    """
    import stripe as stripe_sdk

    if not signature or not is_configured():
        return None
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        return None
    try:
        event = stripe_sdk.Webhook.construct_event(raw_body, signature, secret)
    except ValueError:  # invalid payload
        return None
    except stripe_sdk.StripeError:  # invalid signature
        return None
    return event


def session_is_paid(payment_status: Any) -> bool:
    return str(payment_status or "").lower() in {"paid", "no_payment_required"}


def session_is_expired(status: Any) -> bool:
    """An expired session can never complete, so the payment row fails."""
    return str(status or "").lower() == "expired"
