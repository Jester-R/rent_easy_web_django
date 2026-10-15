"""Shared helper for owner payout-account fields."""

from __future__ import annotations

from django.utils import timezone
from django_bolt.exceptions import HTTPException

from accounts.models import PAYOUT_METHOD_VALUES
from core.bolt import body_str

PAYOUT_KEYS = (
    "payout_method",
    "payout_account_name",
    "payout_account_number",
    "payout_bank_name",
    "payout_phone",
    "payout_note",
)


def apply_payout_fields(user, data: dict) -> None:
    """Update an owner's payout account from request data, if supplied."""
    if not any(key in data for key in PAYOUT_KEYS):
        return
    if not getattr(user, "is_owner", False):
        raise HTTPException(status_code=403, detail="owner_required")
    if "payout_method" in data:
        method = body_str(data, "payout_method").strip().lower()
        if method and method not in PAYOUT_METHOD_VALUES:
            raise HTTPException(status_code=422, detail="payout_method_invalid")
        user.payout_method = method
    if "payout_account_name" in data:
        user.payout_account_name = body_str(data, "payout_account_name").strip()[:120]
    if "payout_account_number" in data:
        user.payout_account_number = body_str(data, "payout_account_number").strip()[
            :64
        ]
    if "payout_bank_name" in data:
        user.payout_bank_name = body_str(data, "payout_bank_name").strip()[:120]
    if "payout_phone" in data:
        user.payout_phone = body_str(data, "payout_phone").strip()[:32]
    if "payout_note" in data:
        user.payout_note = body_str(data, "payout_note").strip()[:255]
    user.payout_updated_at = timezone.now()
