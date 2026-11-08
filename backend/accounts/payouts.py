"""Shared helper for owner payout-account fields."""

from __future__ import annotations

from django.utils import timezone
from django_bolt.exceptions import HTTPException

from core.bolt import body_str

PAYOUT_METHOD_VALUES = {"aba"}

PAYOUT_KEYS = (
    "payout_method",
    "payout_accounts",
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
    if "payout_accounts" in data:
        raw_accounts = data.get("payout_accounts")
        if not isinstance(raw_accounts, dict):
            raise HTTPException(status_code=422, detail="payout_accounts_invalid")
        clean_accounts = {}
        limits = {
            "account_name": 120,
            "account_number": 64,
            "bank_name": 120,
            "phone": 32,
            "note": 255,
        }
        for method, account in raw_accounts.items():
            method = str(method).strip().lower()
            if method not in PAYOUT_METHOD_VALUES or not isinstance(account, dict):
                raise HTTPException(status_code=422, detail="payout_accounts_invalid")
            clean_accounts[method] = {
                key: body_str(account, key).strip()[:limit]
                for key, limit in limits.items()
            }
        user.payout_accounts = clean_accounts
    if "payout_method" in data:
        method = body_str(data, "payout_method").strip().lower()
        if method and method not in PAYOUT_METHOD_VALUES:
            raise HTTPException(status_code=422, detail="payout_method_invalid")
        previous_method = user.payout_method
        if (
            previous_method
            and previous_method != method
            and "payout_accounts" not in data
        ):
            accounts = (
                user.payout_accounts if isinstance(user.payout_accounts, dict) else {}
            )
            if previous_method not in accounts:
                accounts = {
                    **accounts,
                    previous_method: user.get_payout_account(previous_method),
                }
                user.payout_accounts = accounts
        user.payout_method = method
    account = user.get_payout_account()
    # Older clients still submit the selected method's fields directly. Map
    # those values into only that method's entry for backwards compatibility.
    for field, key, limit in (
        ("payout_account_name", "account_name", 120),
        ("payout_account_number", "account_number", 64),
        ("payout_bank_name", "bank_name", 120),
        ("payout_phone", "phone", 32),
        ("payout_note", "note", 255),
    ):
        if field in data:
            account[key] = body_str(data, field).strip()[:limit]
    if user.payout_method:
        if user.payout_method == "aba":
            account["bank_name"] = "ABA Bank"
        user.payout_accounts = {
            **(user.payout_accounts if isinstance(user.payout_accounts, dict) else {}),
            user.payout_method: account,
        }
    user.payout_account_name = account["account_name"]
    user.payout_account_number = account["account_number"]
    user.payout_bank_name = account["bank_name"]
    user.payout_phone = account["phone"]
    user.payout_note = account["note"]
    user.payout_updated_at = timezone.now()
