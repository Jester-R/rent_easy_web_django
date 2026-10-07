"""Payments JSON endpoints: renter receipts, owner revenue, refund processing.

Handlers are native async Django-Bolt handlers; the sync refund service hops
through :func:`core.bolt.in_thread`.
"""

from __future__ import annotations

from django.db.models import Count, Q, Sum
from django_bolt import BoltAPI
from django_bolt.exceptions import HTTPException

from core.bolt import (
    in_thread,
    mark_full_request,
    owner_required,
    param_int,
    q,
    renter_required,
)
from core.bolt_serializers import payment as serialize_payment
from core.bolt_serializers import refund as serialize_refund
from payments.models import Payment, Refund
from payments.services import process_refund

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
    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "query": search,
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
    return {"payment": await serialize_payment(payment), "audience": "renter"}


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------


@api.get("/owner/payments/")
async def owner_list(request):
    user = await owner_required(request)
    queryset = (
        Payment.objects.filter(property__owner=user)
        .select_related("property", "booking", "user")
        .order_by("-created_at")
    )
    queryset = _apply_filters(queryset, request)

    agg = await Payment.objects.filter(property__owner=user).aaggregate(
        revenue=Sum("amount", filter=Q(status=Payment.Status.SUCCESS)),
        refunded=Sum("refunded_amount"),
        count=Count("id"),
    )
    pending_refunds = (
        Refund.objects.filter(booking__owner=user, status=Refund.Status.PENDING)
        .select_related(
            "payment",
            "booking",
            "booking__renter",
            "payment__property",
            "payment__property__owner",
            "payment__user",
        )
        .order_by("-created_at")
    )
    renter_count = await (
        Payment.objects.filter(property__owner=user)
        .values("user_id")
        .distinct()
        .acount()
    )
    return {
        "payments": [await serialize_payment(p) async for p in queryset],
        "pending_refunds": [
            await serialize_refund(r) async for r in pending_refunds
        ],
        "renter_count": renter_count,
        "totals": {
            "revenue": float(agg["revenue"] or 0),
            "refunded": float(agg["refunded"] or 0),
            "count": agg["count"] or 0,
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
    return {"payment": await serialize_payment(payment), "audience": "owner"}


@api.post("/owner/payments/refunds/{pk}/process/")
async def process_refund_view(request):
    pk = param_int(request, "pk")
    user = await owner_required(request)
    refund = await (
        Refund.objects.select_related("payment", "payment__property", "booking")
        .filter(pk=pk)
        .afirst()
    )
    if refund is None:
        raise HTTPException(status_code=404, detail="refund_not_found")
    payment = refund.payment
    if payment.property_id and payment.property.owner_id != user.pk:
        raise HTTPException(status_code=403, detail="not_authorized")
    ok = await in_thread(process_refund, refund, actor=user)
    if not ok:
        raise HTTPException(status_code=409, detail="refund_already_processed")
    return {"ok": True, "refund": await serialize_refund(refund)}


mark_full_request(api)

__all__ = ["api"]