from __future__ import annotations

from django import forms
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from listings.models import Property
from payments.models import Payment

from .models import Booking, BookingStatus

BOOKING_STATUS_FILTERS = ("all", "Pending", "Approved", "Rejected", "Cancelled")


def apply_status_filter(queryset, raw: str):
    value = (raw or "all").strip()
    if value in BOOKING_STATUS_FILTERS and value != "all":
        return queryset.filter(status=value)
    return queryset


def focus_queryset(queryset, focus_id):
    if focus_id:
        return queryset.order_by("-created_at")
    return queryset


class BookingFilter:
    """Small helper that normalises GET params for the bookings screens."""

    def __init__(self, request):
        self.status = (request.GET.get("status") or "all").strip()
        if self.status not in BOOKING_STATUS_FILTERS:
            self.status = "all"
        raw_focus = (request.GET.get("focus") or "").strip()
        try:
            self.focus = int(raw_focus) if raw_focus else None
        except ValueError:
            self.focus = None

    @property
    def query_string(self) -> str:
        parts = []
        if self.status != "all":
            parts.append(f"status={self.status}")
        if self.focus:
            parts.append(f"focus={self.focus}")
        return "&".join(parts)


class PayBookingForm(forms.Form):
    """Mock checkout — mirrors the app's Pay Now dialog."""

    method = forms.ChoiceField(choices=Payment.Method.choices, label="Payment Method", initial=Payment.Method.ABA)
    simulate = forms.ChoiceField(
        required=False,
        choices=(("", "Random (90% success)"), ("success", "Force success"), ("failed", "Force failure")),
        label="Gateway outcome",
    )


class BookingAdminForm(forms.ModelForm):
    """Superadmin console booking editor."""

    status = forms.ChoiceField(choices=BookingStatus.choices, label="Status")

    class Meta:
        model = Booking
        fields = ["status", "monthly_rent", "lease_months", "note", "move_in_date"]
        widgets = {
            "monthly_rent": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "lease_months": forms.NumberInput(attrs={"min": "1", "max": "120"}),
            "move_in_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
            "status": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"


class BookingCreateAdminForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["property", "renter", "owner", "status", "monthly_rent", "lease_months", "move_in_date", "note"]
        widgets = {
            "property": forms.Select(),
            "renter": forms.Select(),
            "owner": forms.Select(),
            "status": forms.Select(),
            "monthly_rent": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "lease_months": forms.NumberInput(attrs={"min": "1", "max": "120"}),
            "move_in_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

    def clean(self):
        cleaned = super().clean()
        prop: Property | None = cleaned.get("property")
        if prop is not None:
            if not cleaned.get("owner"):
                cleaned["owner"] = prop.owner
            if not cleaned.get("monthly_rent"):
                cleaned["monthly_rent"] = prop.price_per_month
        return cleaned


def booking_owner_queryset(user):
    return (
        Booking.objects.filter(owner=user)
        .select_related("property", "renter", "owner", "payment")
        .order_by("-created_at")
    )


def booking_renter_queryset(user):
    return (
        Booking.objects.filter(renter=user)
        .select_related("property", "renter", "owner", "payment")
        .order_by("-created_at")
    )


def booking_all_queryset():
    return Booking.objects.select_related("property", "renter", "owner", "payment").order_by("-created_at")


def search_bookings(queryset, query: str):
    query = (query or "").strip()
    if not query:
        return queryset
    return queryset.filter(
        Q(property__title__icontains=query)
        | Q(renter__email__icontains=query)
        | Q(renter__full_name__icontains=query)
        | Q(owner__email__icontains=query)
        | Q(owner__full_name__icontains=query)
    )


def get_booking_for(pk: int) -> Booking:
    return get_object_or_404(
        Booking.objects.select_related("property", "renter", "owner", "payment"), pk=pk
    )


def redirect_back(request, fallback: str):
    target = request.POST.get("next") or request.GET.get("next")
    if target and target.startswith("/"):
        return redirect(target)
    return redirect(reverse(fallback))
