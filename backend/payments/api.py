"""Payments JSON endpoints: renter receipts, owner revenue, refund processing.

Handlers are native async Django-Bolt handlers; the sync refund service hops
through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Count, Q, Sum
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException
from django_bolt.responses import Redirect

from core.bolt import (
    admin_required,
    body_bool,
    body_str,
    in_thread,
    json_body,
    mark_full_request,
    pagination,
    owner_required,
    param_int,
    q,
    renter_required,
)
from core.bolt_serializers import payment as serialize_payment
from core.bolt_serializers import payout as serialize_payout
from core.bolt_serializers import refund as serialize_refund
from payments.gateways import aba as aba_gateway
from payments.models import Payment, Payout, Refund
from payments.services import (
    RefundRequiresGateway,
    RefundRequestError,
    apply_aba_callback,
    backfill_missing_payouts,
    process_refund,
    request_refund,
    reconcile_aba_payment,
    release_due_payouts,
)

api = BoltAPI(
    django_middleware={"exclude": ["django.middleware.csrf.CsrfViewMiddleware"]},
    trailing_slash="keep",
)


def _apply_filters(queryset, request):
    status = q(request, "status", "all")
    if status and status != "all":
        if status == "Refunded":
            queryset = queryset.filter(refund_status=Payment.RefundStatus.PROCESSED)
        else:
            queryset = queryset.filter(status=status)
    refund = q(request, "refund", "all")
    if refund and refund != "all":
        queryset = queryset.filter(refund_status=refund)
    method = q(request, "method", "all")
    if method and method != "all":
        queryset = queryset.filter(method=method)
    return queryset


def _frontend_payment_url(payment_id: int | None) -> str:
    if payment_id:
        return f"{settings.FRONTEND_BASE_URL}/payments/{payment_id}"
    return f"{settings.FRONTEND_BASE_URL}/payments"


def _payway_signature(request) -> str:
    headers = getattr(request, "headers", {}) or {}
    for key in (
        "x-payway-hmac-sha512",
        "X-PayWay-HMAC-SHA512",
        "X-PAYWAY-HMAC-SHA512",
    ):
        value = headers.get(key)
        if value:
            return str(value)
    try:
        items = headers.items()
    except AttributeError:
        return ""
    for key, value in items:
        if str(key).lower() == "x-payway-hmac-sha512":
            return str(value)
    return ""


async def _refresh_pending_payment(payment: Payment) -> Payment:
    """Ask PayWay to reconcile a pending ABA payment, then reload the row."""
    if (
        payment.provider == Payment.Provider.ABA_PAYWAY
        and payment.is_pending
        and aba_gateway.is_configured()
    ):
        try:
            await in_thread(reconcile_aba_payment, payment)
        except aba_gateway.PayWayError as exc:
            # PayWay has not recorded the transaction yet (for example the
            # browser returned before the checkout was submitted). Keep the
            # payment pending so the next poll can pick it up.
            if exc.code == "6":
                return payment
            raise HTTPException(
                status_code=502, detail="aba_payway_unavailable"
            ) from exc
        except Exception as exc:  # network failure: keep the pending row
            raise HTTPException(
                status_code=502, detail="aba_payway_unavailable"
            ) from exc
        payment = (
            await Payment.objects.select_related("property", "booking", "user")
            .filter(pk=payment.pk)
            .afirst()
        ) or payment
    return payment


# ---------------------------------------------------------------------------
# ABA PayWay callbacks
# ---------------------------------------------------------------------------


@api.post("/payments/aba/callback/")
async def aba_callback(request):
    """Server-to-server notification from PayWay.

    The signature covers the whole JSON body with keys sorted ascending, so the
    raw bytes must be verified before parsing.
    """
    raw_body = getattr(request, "body", b"") or b""
    signature = _payway_signature(request)
    if not aba_gateway.verify_callback_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="invalid_signature")

    import json

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="invalid_payload")

    applied = await in_thread(apply_aba_callback, payload)
    return {"ok": True, "applied": applied}


@api.get("/payments/aba/return/")
async def aba_return(request):
    """Browser return after hosted checkout: reconcile, then land on the receipt."""
    raw_id = q(request, "payment")
    payment_id = None
    try:
        payment_id = int(raw_id)
    except TypeError, ValueError:
        payment_id = None

    if payment_id:
        payment = await (
            Payment.objects.select_related("property", "booking", "user")
            .filter(pk=payment_id)
            .afirst()
        )
        if payment is not None:
            try:
                await _refresh_pending_payment(payment)
            except HTTPException:
                pass

    return Redirect(_frontend_payment_url(payment_id), status_code=303)


@api.post("/rent/payments/{pk}/refresh/")
async def renter_refresh(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    payment = await (
        Payment.objects.select_related("property", "booking", "user")
        .filter(pk=pk)
        .afirst()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    if payment.user_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    payment = await _refresh_pending_payment(payment)
    return {"payment": await serialize_payment(payment)}


@api.post("/owner/payments/{pk}/refresh/")
async def owner_refresh(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    payment = await (
        Payment.objects.select_related("property", "booking", "user")
        .filter(pk=pk)
        .afirst()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    if payment.property_id and payment.property.owner_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    payment = await _refresh_pending_payment(payment)
    return {"payment": await serialize_payment(payment)}


# ---------------------------------------------------------------------------
# Renter
# ---------------------------------------------------------------------------


@api.get("/rent/payments/")
async def renter_list(request):
    user = await renter_required(request)
    queryset = (
        Payment.objects.filter(user=user)
        .select_related("property", "booking", "user")
        .order_by("-created_at")
    )
    queryset = _apply_filters(queryset, request)
    search = q(request, "q")
    if search:
        queryset = queryset.filter(
            Q(property__title__icontains=search)
            | Q(reference__icontains=search)
            | Q(property__location__icontains=search)
        )
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]
    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "query": search,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@api.get("/rent/payments/{pk}/")
async def renter_detail(request):
    pk = param_int(request, "pk")
    user = await renter_required(request)
    payment = await (
        Payment.objects.select_related("property", "booking", "user")
        .filter(pk=pk)
        .afirst()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    if payment.user_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    refund = await Refund.objects.select_related("payment", "requested_by").filter(
        payment_id=pk
    ).order_by("-created_at").afirst()
    return {
        "payment": await serialize_payment(payment),
        "refund": await serialize_refund(refund) if refund else None,
        "audience": "renter",
    }


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------


@api.get("/owner/payments/")
async def owner_list(request):
    user = await owner_required(request)

    await in_thread(backfill_missing_payouts, owner=user)
    await in_thread(release_due_payouts, owner=user)

    queryset = (
        Payment.objects.filter(property__owner=user)
        .select_related("property", "booking", "user")
        .order_by("-created_at")
    )
    queryset = _apply_filters(queryset, request)
    search = q(request, "q")
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(property__title__icontains=search)
            | Q(user__full_name__icontains=search)
            | Q(user__email__icontains=search)
        )
    page, page_size = pagination(request)
    total = await queryset.acount()
    queryset = queryset[(page - 1) * page_size : page * page_size]

    agg = await Payment.objects.filter(property__owner=user).aaggregate(
        revenue=Sum("amount", filter=Q(status=Payment.Status.SUCCESS)),
        refunded=Sum("refunded_amount"),
        count=Count("id"),
    )
    pending_refunds = (
        Refund.objects.filter(booking__owner=user, status=Refund.Status.PENDING)
        .select_related(
            "payment",
            "requested_by",
            "booking",
            "booking__renter",
            "payment__property",
            "payment__property__owner",
            "payment__user",
        )
        .order_by("-created_at")
    )
    refund_page, refund_page_size = pagination(
        request, page_key="refund_page", size_key="refund_page_size"
    )
    refunds_total = await pending_refunds.acount()
    pending_refunds = pending_refunds[
        (refund_page - 1) * refund_page_size : refund_page * refund_page_size
    ]
    renter_count = await (
        Payment.objects.filter(property__owner=user)
        .values("user_id")
        .distinct()
        .acount()
    )
    payouts = (
        Payout.objects.filter(owner=user)
        .select_related(
            "owner",
            "payment",
            "payment__property",
            "payment__booking",
            "payment__booking__property",
        )
        .order_by("-created_at")
    )
    payout_page, payout_page_size = pagination(
        request, page_key="payout_page", size_key="payout_page_size"
    )
    payouts_total = await payouts.acount()
    payouts = payouts[
        (payout_page - 1) * payout_page_size : payout_page * payout_page_size
    ]
    payout_agg = await Payout.objects.filter(owner=user).aaggregate(
        scheduled=Sum("amount", filter=Q(status=Payout.Status.SCHEDULED)),
        eligible=Sum("amount", filter=Q(status=Payout.Status.ELIGIBLE)),
        paid=Sum("amount", filter=Q(status=Payout.Status.PAID)),
    )
    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pending_refunds": [await serialize_refund(r) async for r in pending_refunds],
        "refunds_total": refunds_total,
        "refund_page": refund_page,
        "refund_page_size": refund_page_size,
        "renter_count": renter_count,
        "totals": {
            "revenue": float(agg["revenue"] or 0),
            "refunded": float(agg["refunded"] or 0),
            "count": agg["count"] or 0,
        },
        "payouts": [await serialize_payout(p) async for p in payouts],
        "payouts_total": payouts_total,
        "payout_page": payout_page,
        "payout_page_size": payout_page_size,
        "payout_totals": {
            "scheduled": float(payout_agg["scheduled"] or 0),
            "eligible": float(payout_agg["eligible"] or 0),
            "paid": float(payout_agg["paid"] or 0),
        },
        "payout_account": {
            "method": user.payout_method,
            "account_name": user.payout_account_name,
            "account_number": user.payout_account_number,
            "bank_name": user.payout_bank_name,
            "phone": user.payout_phone,
            "note": user.payout_note,
            "ready": user.has_payout_details,
        },
    }


@api.get("/owner/payments/{pk}/")
async def owner_detail(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    payment = await (
        Payment.objects.select_related("property", "booking", "user")
        .filter(pk=pk)
        .afirst()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    if payment.property_id and payment.property.owner_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    refund = await (
        Refund.objects.select_related("payment", "booking", "requested_by")
        .filter(payment_id=pk, booking__owner=user)
        .order_by("-created_at")
        .afirst()
    )
    return {
        "payment": await serialize_payment(payment),
        "refund": await serialize_refund(refund) if refund else None,
        "audience": "owner",
    }


@api.post("/payments/{pk}/refund/request/")
async def refund_request_view(request):
    pk = param_int(request, "pk")
    user = await login_required(request)
    payment = await Payment.objects.filter(pk=pk).afirst()
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    data = json_body(request)
    try:
        refund = await in_thread(
            request_refund,
            payment,
            user,
            body_str(data, "reason") or Refund.Reason.OTHER,
            body_str(data, "request_note"),
        )
    except RefundRequestError as exc:
        status = 403 if exc.code == "not_authorized" else 409
        raise HTTPException(status_code=status, detail=exc.code) from exc
    return {"refund": await serialize_refund(refund)}


@api.post("/owner/payments/refunds/{pk}/process/")
async def process_refund_view(request):
    pk = param_int(request, "pk")
    user = await admin_required(request)
    refund = await (
        Refund.objects.select_related(
            "payment",
            "payment__property",
            "payment__user",
            "booking",
            "booking__owner",
        )
        .filter(pk=pk)
        .afirst()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="refund_not_found")
    data = json_body(request)
    try:
        ok = await in_thread(
            process_refund,
            refund,
            actor=user,
            external=body_bool(data, "external"),
            note=body_str(data, "note"),
        )
    except RefundRequiresGateway as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if not ok:
        raise HTTPException(status_code=409, detail="refund_already_processed")
    refund = await (
        Refund.objects.select_related(
            "payment",
            "payment__property",
            "payment__user",
            "booking",
            "booking__owner",
        )
        .filter(pk=pk)
        .afirst()
    )
    return {"ok": True, "refund": await serialize_refund(refund)}


mark_full_request(api)

__all__ = ["api"]
