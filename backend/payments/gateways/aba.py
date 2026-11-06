"""ABA PayWay (Ecommerce Checkout) client.

PayWay signs every request with ``base64(HMAC-SHA512(concatenated_fields,
api_key))``.  The field order differs per endpoint and is *not* discoverable
from the response: a wrong order produces a generic "Wrong hash" error, so the
exact ABA order is kept in :data:`PURCHASE_HASH_FIELDS` and
:data:`CHECK_HASH_FIELDS`.

The hosted-checkout helper remains available, and renter checkout uses the QR flow:

1. :func:`create_qr_payment` requests a signed KHQR and its data image.
2. PayWay POSTs the result to ``ABA_PAYWAY_CALLBACK_URL``; the payload is
   verified by :func:`verify_callback_signature`.
3. :func:`check_transaction` is the authoritative reconciliation path used by
   the return/refresh endpoints (useful when the callback cannot reach a
   local development server).

Docs: https://developer.payway.com.kh/qr-api-14530840e0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

PURCHASE_HASH_FIELDS: tuple[str, ...] = (
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

CHECK_HASH_FIELDS: tuple[str, ...] = ("req_time", "merchant_id", "tran_id")

PURCHASE_PATH = "/api/payment-gateway/v1/payments/purchase"
CHECK_PATH = "/api/payment-gateway/v1/payments/check-transaction-2"
QR_PATH = "/api/payment-gateway/v1/payments/generate-qr"
QR_HASH_FIELDS: tuple[str, ...] = (
    "req_time",
    "merchant_id",
    "tran_id",
    "amount",
    "items",
    "first_name",
    "last_name",
    "email",
    "phone",
    "purchase_type",
    "payment_option",
    "callback_url",
    "return_deeplink",
    "currency",
    "custom_fields",
    "return_params",
    "payout",
    "lifetime",
    "qr_image_template",
)

_SUCCESS_CODES = {"0", "00"}
_APPROVED_STATUSES = {"APPROVED", "PRE-AUTH"}


class PayWayError(RuntimeError):
    """A PayWay API call returned an error or was unreachable."""

    def __init__(self, code: str, message: str, payload: dict | None = None):
        self.code = str(code or "")
        self.message = message or "PayWay request failed"
        self.payload = payload or {}
        super().__init__(f"{self.code}: {self.message}" if self.code else self.message)


def merchant_id() -> str:
    """Return the admin-configured merchant ID, falling back to environment config."""
    try:
        from accounts.models import PlatformSettings

        configured = (
            PlatformSettings.objects.filter(pk=1)
            .values_list("aba_payway_merchant_id", flat=True)
            .first()
        )
    except OperationalError, ProgrammingError:  # migration/setup not complete yet
        configured = ""
    return str(configured or settings.ABA_PAYWAY_MERCHANT_ID or "").strip()


def is_configured() -> bool:
    """Whether real PayWay calls are enabled for this environment."""
    return bool(
        getattr(settings, "ABA_PAYWAY_ENABLED", False)
        and merchant_id()
        and getattr(settings, "ABA_PAYWAY_API_KEY", "")
    )


def amount_to_string(value: Decimal | int | float | str) -> str:
    """Render an amount the way PayWay's signature expects (``0.10`` -> ``0.1``)."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayWayError("invalid_amount", f"Invalid amount: {value!r}") from exc
    if amount != amount.to_integral_value():
        return format(amount.normalize(), "f")
    return str(amount.quantize(Decimal("1")))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _b64_json(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def hash_fields(fields: dict[str, Any], *, api_key: str | None = None) -> str:
    """Return the base64 HMAC-SHA512 of ``fields`` in the documented order."""
    key = api_key if api_key is not None else settings.ABA_PAYWAY_API_KEY
    before_hash = "".join(
        str(fields.get(name, "") or "") for name in PURCHASE_HASH_FIELDS
    )
    return _sign(before_hash, key)


def _hash_check_fields(fields: dict[str, Any], *, api_key: str | None = None) -> str:
    key = api_key if api_key is not None else settings.ABA_PAYWAY_API_KEY
    before_hash = "".join(str(fields.get(name, "") or "") for name in CHECK_HASH_FIELDS)
    return _sign(before_hash, key)


def _sign(value: str, api_key: str) -> str:
    digest = hmac.new(
        api_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha512
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{settings.ABA_PAYWAY_BASE_URL}{CHECK_PATH}",
        json=data,
        timeout=settings.ABA_PAYWAY_TIMEOUT_SECONDS,
    )
    try:
        body = response.json()
    except ValueError as exc:  # pragma: no cover - defensive
        raise PayWayError(
            "invalid_response", f"PayWay returned HTTP {response.status_code}"
        ) from exc
    if not isinstance(body, dict):
        raise PayWayError("invalid_response", "PayWay returned a non-object response")
    return body


def create_qr_payment(
    *,
    tran_id: str,
    amount: Decimal | int | float | str,
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    phone: str = "",
    items: list[dict[str, Any]] | None = None,
    return_params: str = "",
) -> dict[str, Any]:
    """Create a PayWay KHQR and return its image data from the server."""
    if not is_configured():
        raise PayWayError("not_configured", "ABA PayWay is not configured")
    mid = merchant_id()
    if not mid:
        raise PayWayError("not_configured", "ABA PayWay merchant ID is not configured")
    callback = base64.b64encode(settings.ABA_PAYWAY_CALLBACK_URL.encode()).decode(
        "ascii"
    )
    fields: dict[str, Any] = {
        "req_time": _now(),
        "merchant_id": mid,
        "tran_id": str(tran_id)[:20],
        "first_name": firstname[:20],
        "last_name": lastname[:20],
        "email": email[:50],
        "phone": phone[:20],
        "amount": amount_to_string(amount),
        "purchase_type": "purchase",
        "payment_option": "abapay_khqr",
        "items": _b64_json(items or []),
        "currency": settings.ABA_PAYWAY_CURRENCY,
        "callback_url": callback,
        "return_deeplink": "",
        "custom_fields": "",
        "return_params": return_params,
        "payout": "",
        "lifetime": int(settings.ABA_PAYWAY_LIFETIME_MINUTES),
        "qr_image_template": "template3_color",
    }
    before_hash = "".join(str(fields.get(name, "") or "") for name in QR_HASH_FIELDS)
    fields["hash"] = _sign(before_hash, settings.ABA_PAYWAY_API_KEY)
    try:
        response = httpx.post(
            f"{settings.ABA_PAYWAY_BASE_URL}{QR_PATH}",
            json=fields,
            timeout=settings.ABA_PAYWAY_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise PayWayError("unavailable", "Could not connect to ABA PayWay") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise PayWayError(
            "invalid_response", f"PayWay returned HTTP {response.status_code}"
        ) from exc
    if not isinstance(body, dict):
        raise PayWayError("invalid_response", "PayWay returned a non-object response")
    status = body.get("status") or {}
    if str(status.get("code")) not in _SUCCESS_CODES:
        raise PayWayError(
            str(status.get("code") or "unknown"),
            status.get("message") or "PayWay QR generation failed",
            body,
        )
    if not body.get("qrImage"):
        raise PayWayError(
            "invalid_response", "PayWay response did not include a QR image", body
        )
    return {
        "image": body["qrImage"],
        "qr_string": body.get("qrString", ""),
        "deeplink": body.get("abapay_deeplink", ""),
        "amount": body.get("amount", fields["amount"]),
        "currency": body.get("currency", fields["currency"]),
        "expires_in": fields["lifetime"],
    }


def create_purchase_form(
    *,
    tran_id: str,
    amount: Decimal | int | float | str,
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    phone: str = "",
    items: list[dict[str, Any]] | None = None,
    currency: str | None = None,
    return_params: str = "",
) -> dict[str, Any]:
    """Build the signed form fields for PayWay's hosted checkout.

    The caller is responsible for POSTing ``fields`` to ``action_url``. Empty
    optional fields are omitted from the form but still contribute an empty
    string to the hash, matching ABA's PHP sample.
    """
    if not is_configured():
        raise PayWayError("not_configured", "ABA PayWay is not configured")

    payment_id = None
    if return_params:
        try:
            payment_id = json.loads(return_params).get("payment_id")
        except ValueError, AttributeError:
            payment_id = None

    payment_id_text = "" if payment_id is None else str(payment_id)
    callback_url = settings.ABA_PAYWAY_CALLBACK_URL
    continue_url = settings.ABA_PAYWAY_RETURN_URL.format(payment_id=payment_id_text)
    cancel_url = settings.ABA_PAYWAY_CANCEL_URL

    configured_merchant_id = merchant_id()
    if not configured_merchant_id:
        raise PayWayError("not_configured", "ABA PayWay merchant ID is not configured")
    fields: dict[str, str] = {
        "req_time": _now(),
        "merchant_id": configured_merchant_id,
        "tran_id": str(tran_id)[:20],
        "amount": amount_to_string(amount),
        "items": _b64_json(items or []),
        "shipping": "0",
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "phone": phone,
        "type": "purchase",
        "payment_option": settings.ABA_PAYWAY_PAYMENT_OPTION,
        "return_url": base64.b64encode(callback_url.encode("utf-8")).decode("ascii"),
        "cancel_url": cancel_url,
        "continue_success_url": continue_url,
        "return_deeplink": "",
        "currency": currency or settings.ABA_PAYWAY_CURRENCY,
        "custom_fields": "",
        "return_params": return_params,
        "payout": "",
        "lifetime": str(settings.ABA_PAYWAY_LIFETIME_MINUTES),
        "additional_params": "",
        "google_pay_token": "",
        "skip_success_page": "1",
    }
    fields["hash"] = hash_fields(fields)
    return {
        "provider": "aba_payway",
        "action_url": f"{settings.ABA_PAYWAY_BASE_URL}{PURCHASE_PATH}",
        "method": "POST",
        "fields": {key: value for key, value in fields.items() if value != ""},
    }


def check_transaction(
    tran_id: str, *, merchant_id_override: str | None = None
) -> dict[str, Any]:
    """Fetch the authoritative transaction status from PayWay."""
    if not is_configured():
        raise PayWayError("not_configured", "ABA PayWay is not configured")
    transaction_merchant_id = merchant_id_override or merchant_id()
    if not transaction_merchant_id:
        raise PayWayError("not_configured", "ABA PayWay merchant ID is not configured")
    fields = {
        "req_time": _now(),
        "merchant_id": transaction_merchant_id,
        "tran_id": str(tran_id)[:20],
    }
    fields["hash"] = _hash_check_fields(fields)
    body = _payload(fields)
    status = body.get("status") or {}
    code = status.get("code")
    if str(code) not in _SUCCESS_CODES:
        raise PayWayError(
            str(code or "unknown"),
            status.get("message") or "PayWay check-transaction failed",
            body,
        )
    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise PayWayError(
            "invalid_response", "PayWay returned no transaction data", body
        )
    return data


def status_is_approved(value: Any) -> bool:
    return str(value or "").upper() in _APPROVED_STATUSES


def verify_callback_signature(raw_body: bytes, signature: str) -> bool:
    """Verify the ``X-PayWay-HMAC-SHA512`` header on a callback payload."""
    if not signature or not is_configured():
        return False
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except ValueError, UnicodeDecodeError:
        return False
    if not isinstance(payload, dict):
        return False

    before_hash = "".join(_callback_value(payload[key]) for key in sorted(payload))
    expected = _sign(before_hash, settings.ABA_PAYWAY_API_KEY)
    return hmac.compare_digest(expected, signature)


def _callback_value(value: Any) -> str:
    """Mirror PHP's string concatenation of a decoded JSON value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        # PHP casts true/false to "1"/"" during concatenation.
        return "1" if value else ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # PHP drops the trailing ".0" and uses 14 significant digits by default.
        if value.is_integer():
            return str(int(value))
        return format(value, ".14g")
    if isinstance(value, str):
        return value
    # PHP's json_encode escapes forward slashes by default. PayWay callbacks
    # normally only contain scalars, but keep nested values compatible.
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace(
        "/", "\\/"
    )
