from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from bookings.models import Booking
from core.decorators import role_guard
from listings.models import Property
from payments.services import process_refund

from .models import Payment, Refund


class PaymentFilterForm(forms.Form):
    status = forms.ChoiceField(
        required=False,
        choices=(
            ("all", "All"),
            ("Success", "Success"),
            ("Failed", "Failed"),
            ("Refunded", "Refunded"),
        ),
    )
    refund = forms.ChoiceField(
        required=False,
        choices=(("all", "All"), ("None", "None"), ("Pending", "Pending"), ("Processed", "Processed")),
    )
    q = forms.CharField(required=False)
    method = forms.ChoiceField(required=False, choices=(("all", "All"),) + tuple(Payment.Method.choices))


class PaymentAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "status", "refund_status", "refunded_amount"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "refunded_amount": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "method": forms.Select(),
            "status": forms.Select(),
            "refund_status": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"


class PaymentCreateAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["property", "user", "booking", "amount", "method", "status"]
        widgets = {
            "property": forms.Select(),
            "user": forms.Select(),
            "booking": forms.Select(),
            "amount": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "method": forms.Select(),
            "status": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("amount"):
            booking = cleaned.get("booking")
            prop = cleaned.get("property")
            if booking:
                cleaned["amount"] = booking.monthly_rent
            elif prop:
                cleaned["amount"] = prop.price_per_month
        return cleaned


@require_GET
@login_required
@role_guard("is_renter")
def renter_list(request):
    form = PaymentFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    if not form.is_valid():
        form = PaymentFilterForm()

    queryset = (
        Payment.objects.filter(user=request.user)
        .select_related("property", "booking", "user")
        .order_by("-created_at")
    )
    if data.get("status") and data["status"] != "all":
        if data["status"] == "Refunded":
            queryset = queryset.filter(refund_status=Payment.RefundStatus.PROCESSED)
        else:
            queryset = queryset.filter(status=data["status"])
    if data.get("refund") and data["refund"] != "all":
        queryset = queryset.filter(refund_status=data["refund"])
    if data.get("method") and data["method"] != "all":
        queryset = queryset.filter(method=data["method"])
    if (query := (data.get("q") or "").strip()):
        queryset = queryset.filter(
            Q(property__title__icontains=query) | Q(reference__icontains=query) | Q(property__location__icontains=query)
        )

    focus_raw = (request.GET.get("focus") or "").strip()
    try:
        focus = int(focus_raw) if focus_raw else None
    except ValueError:
        focus = None

    return render(
        request,
        "payments/renter_list.html",
        {"payments": list(queryset), "form": form, "focus": focus, "query": (data.get("q") or "")},
    )


@require_GET
@login_required
@role_guard("is_renter")
def renter_detail(request, pk: int):
    payment = get_object_or_404(Payment.objects.select_related("property", "booking", "user"), pk=pk)
    if payment.user_id != request.user.pk:
        return render(request, "accounts/denied.html", status=403)
    return render(request, "payments/renter_detail.html", {"payment": payment})


@require_GET
@login_required
@role_guard("is_owner")
def owner_list(request):
    """Owner's revenue view: payments received against their properties."""
    form = PaymentFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    if not form.is_valid():
        form = PaymentFilterForm()

    queryset = (
        Payment.objects.filter(property__owner=request.user)
        .select_related("property", "booking", "user")
        .order_by("-created_at")
    )
    if data.get("status") and data["status"] != "all":
        if data["status"] == "Refunded":
            queryset = queryset.filter(refund_status=Payment.RefundStatus.PROCESSED)
        else:
            queryset = queryset.filter(status=data["status"])
    if data.get("refund") and data["refund"] != "all":
        queryset = queryset.filter(refund_status=data["refund"])
    if data.get("method") and data["method"] != "all":
        queryset = queryset.filter(method=data["method"])

    agg = Payment.objects.filter(property__owner=request.user).aggregate(
        revenue=Sum("amount", filter=Q(status=Payment.Status.SUCCESS)),
        refunded=Sum("refunded_amount"),
        count=Count("id"),
    )
    pending_refunds = list(
        Refund.objects.filter(booking__owner=request.user, status=Refund.Status.PENDING)
        .select_related("payment", "booking", "booking__renter")
        .order_by("-created_at")
    )
    renter_count = (
        Payment.objects.filter(property__owner=request.user).values("user_id").distinct().count()
    )
    return render(
        request,
        "payments/owner_list.html",
        {
            "payments": list(queryset),
            "form": form,
            "pending_refunds": pending_refunds,
            "renter_count": renter_count,
            "agg": {
                "revenue": float(agg["revenue"] or 0),
                "refunded": float(agg["refunded"] or 0),
                "count": agg["count"] or 0,
            },
        },
    )


@require_GET
@login_required
@role_guard("is_owner")
def owner_detail(request, pk: int):
    payment = get_object_or_404(Payment.objects.select_related("property", "booking", "user"), pk=pk)
    if payment.property_id and payment.property.owner_id != request.user.pk:
        return render(request, "accounts/denied.html", status=403)
    return render(request, "payments/renter_detail.html", {"payment": payment, "audience": "owner"})


@require_POST
@login_required
@role_guard("is_owner")
def process_refund_view(request, pk: int):
    refund = get_object_or_404(Refund.objects.select_related("payment", "booking"), pk=pk)
    payment = refund.payment
    if payment.property_id and payment.property.owner_id != request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect("payments:owner_list")
    ok = process_refund(refund, actor=request.user)
    request.session["renteasy_flash"] = "refund_processed" if ok else "not_authorized"
    return redirect("payments:owner_list")
