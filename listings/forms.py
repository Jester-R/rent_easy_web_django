from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Property


class PropertyForm(forms.ModelForm):
    """Add / edit listing form — same fields as the app's AddPropertyScreen."""

    class Meta:
        model = Property
        fields = ["title", "location", "price_per_month", "bedrooms", "bathrooms", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Modern Studio Near Downtown", "maxlength": 160}),
            "location": forms.TextInput(attrs={"placeholder": "Phnom Penh - BKK1", "maxlength": 160}),
            "price_per_month": forms.NumberInput(attrs={"min": "0", "step": "1", "placeholder": "450"}),
            "bedrooms": forms.NumberInput(attrs={"min": "0", "max": "99", "step": "1"}),
            "bathrooms": forms.NumberInput(attrs={"min": "0", "max": "99", "step": "1"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Bright studio apartment…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bedrooms"].initial = 2
        self.fields["bathrooms"].initial = 1
        for name, field in self.fields.items():
            widget = field.widget
            if name == "description":
                continue
            widget.attrs["class"] = "form-input"
        self.fields["description"].widget.attrs["class"] = "form-input"
        self.order_fields(["title", "location", "price_per_month", "bedrooms", "bathrooms", "description"])

    def clean_price_per_month(self):
        value = self.cleaned_data.get("price_per_month")
        if value in (None, ""):
            raise ValidationError("price_required", code="price_required")
        if float(value) <= 0:
            raise ValidationError("price_required", code="price_required")
        return value

    def clean_bedrooms(self):
        value = self.cleaned_data.get("bedrooms")
        if value in (None, ""):
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            raise ValidationError("invalid_number", code="invalid_number")

    def clean_bathrooms(self):
        value = self.cleaned_data.get("bathrooms")
        if value in (None, ""):
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            raise ValidationError("invalid_number", code="invalid_number")


class BookingRequestForm(forms.Form):
    """Renter's booking request form — mirrors FakePaymentScreen."""

    LEASE_CHOICES = [(6, "6"), (12, "12"), (18, "18"), (24, "24")]

    move_in_date = forms.DateField(
        required=False,
        label="Move-in Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
    lease_months = forms.TypedChoiceField(
        choices=LEASE_CHOICES, coerce=int, initial=12, label="Lease Months", widget=forms.RadioSelect
    )
    note = forms.CharField(
        required=False,
        label="Message to owner",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Tell the owner when you plan to move in…"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["move_in_date"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.fields["move_in_date"].widget.attrs["max"] = (timezone.localdate() + timezone.timedelta(days=365)).isoformat()
        self.fields["note"].widget.attrs["class"] = "form-input"

    def clean_move_in_date(self):
        value = self.cleaned_data.get("move_in_date")
        if value and value < timezone.localdate():
            raise ValidationError("move_in_past", code="move_in_past")
        return value


class PropertyFilterForm(forms.Form):
    """Renter-side search + filter state (GET-driven)."""

    q = forms.CharField(required=False, label="Search")
    location = forms.CharField(required=False, label="Location")
    sort = forms.CharField(required=False, label="Sort by")
    min_bedrooms = forms.IntegerField(required=False, min_value=0, max_value=99, label="Min bedrooms")
    max_price = forms.DecimalField(required=False, min_value=0, max_value=100000, label="Max price")

    SORT_CHOICES = (
        ("recommended", "Recommended"),
        ("price_low", "Price: Low to High"),
        ("price_high", "Price: High to Low"),
        ("bedrooms", "Bedrooms"),
    )

    def clean_sort(self):
        value = (self.cleaned_data.get("sort") or "recommended").strip()
        return value if dict(self.SORT_CHOICES).get(value) else "recommended"

    def clean_min_bedrooms(self):
        value = self.cleaned_data.get("min_bedrooms") or 0
        try:
            return max(0, min(99, int(value)))
        except (TypeError, ValueError):
            return 0

    def clean_max_price(self):
        value = self.cleaned_data.get("max_price")
        if value in (None, ""):
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    @property
    def active_count(self) -> int:
        count = 0
        if self.cleaned_data.get("location"):
            count += 1
        if self.cleaned_data.get("sort", "recommended") != "recommended":
            count += 1
        if self.cleaned_data.get("min_bedrooms"):
            count += 1
        if self.cleaned_data.get("max_price") is not None:
            count += 1
        return count
