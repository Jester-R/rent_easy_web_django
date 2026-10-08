"""Django-Bolt Serializer models for the RentEasy JSON API.

Every entity is a :class:`~django_bolt.serializers.Serializer` — an enhanced
``msgspec.Struct`` subclass.  Instances are built from Django ORM rows with
``afrom_model``/``afrom_models`` (the async loading plan fetches nested
relations lazily), field validators normalise ``Decimal``/``date``/``datetime``
to JSON primitives, and computed fields derive status flags from other fields.

The module-level ``serialize_*`` coroutines preserve the historical dict-
returning call shape used by the API handlers; each ``await``s the serializer
and returns the ``dump()`` (plus any view-specific ``**extra`` keys).
"""

from __future__ import annotations

from datetime import date, datetime

from django_bolt.serializers import Serializer, computed_field, field, field_validator

from bookings.models import ACTIVE_STATUSES, VALID_TRANSITIONS


def _iso(value):
    """date/datetime -> ISO string (``None`` short-circuits, values that are
    already strings pass through so both ``afrom_model`` (datetime) and
    ``afrom_models`` (pre-converted str) paths work)."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value or None


def _num(value):
    """Decimal -> float (JSON-safe number)."""
    return float(value)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserBriefSerializer(Serializer):
    id: int
    email: str
    username: str
    full_name: str
    display_name: str
    role: str


class UserSerializer(UserBriefSerializer):
    is_active: bool
    is_staff: bool
    is_superuser: bool
    is_renter: bool
    is_owner: bool
    is_superadmin_role: bool
    home_url: str
    avatar_hue: int
    date_joined: str
    last_login_at: str | None = None

    @field_validator("date_joined")
    def _dj(cls, value):
        return _iso(value)

    @field_validator("last_login_at")
    def _lla(cls, value):
        return _iso(value)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class PropertySerializer(Serializer):
    id: int
    is_active: bool
    title: str
    location: str
    price_per_month: float
    price_display: str
    location_label: str
    bedrooms: int
    bathrooms: int
    description: str
    owner: UserBriefSerializer
    owner_id: int
    created_at: str
    updated_at: str

    @field_validator("price_per_month")
    def _price(cls, value):
        return _num(value)

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)

    @field_validator("updated_at")
    def _update(cls, value):
        return _iso(value)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


class BookingSerializer(Serializer):
    id: int
    reference: str
    status: str
    monthly_rent: float
    rent_display: str
    move_in_date: str | None = None
    lease_months: int
    note: str
    is_paid: bool
    property: PropertySerializer
    property_id: int
    renter: UserBriefSerializer
    renter_id: int
    owner: UserBriefSerializer
    owner_id: int
    payment_id: int | None = None
    created_at: str
    approved_at: str | None = None
    rejected_at: str | None = None
    cancelled_at: str | None = None

    @field_validator("monthly_rent")
    def _rent(cls, value):
        return _num(value)

    @field_validator("move_in_date")
    def _move(cls, value):
        return _iso(value)

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)

    @field_validator("approved_at")
    def _approve(cls, value):
        return _iso(value)

    @field_validator("rejected_at")
    def _reject(cls, value):
        return _iso(value)

    @field_validator("cancelled_at")
    def _cancel(cls, value):
        return _iso(value)

    @computed_field
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @computed_field
    def can_approve(self) -> bool:
        return "Approved" in VALID_TRANSITIONS.get(self.status, ())

    @computed_field
    def can_reject(self) -> bool:
        return "Rejected" in VALID_TRANSITIONS.get(self.status, ())

    @computed_field
    def can_cancel(self) -> bool:
        if self.status == "Confirmed" and self.is_paid:
            return False
        return "Cancelled" in VALID_TRANSITIONS.get(self.status, ())


# ---------------------------------------------------------------------------
# Payments / refunds
# ---------------------------------------------------------------------------


class PaymentSerializer(Serializer):
    id: int
    reference: str
    amount: float
    amount_display: str
    refunded_amount: float
    refunded_display: str
    method: str
    status: str
    refund_status: str
    is_refunded: bool
    is_successful: bool
    property: PropertySerializer | None = None
    property_id: int | None = None
    property_title: str
    booking_id: int | None = None
    user: UserBriefSerializer
    user_id: int
    created_at: str
    refunded_at: str | None = None

    @field_validator("amount")
    def _amount(cls, value):
        return _num(value)

    @field_validator("refunded_amount")
    def _refunded(cls, value):
        return _num(value)

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)

    @field_validator("refunded_at")
    def _ref_at(cls, value):
        return _iso(value)


class RefundSerializer(Serializer):
    id: int
    reference: str
    amount: float
    amount_display: str
    reason: str
    status: str
    note: str
    payment_id: int
    booking_id: int
    payment: PaymentSerializer
    created_at: str
    processed_at: str | None = None

    @field_validator("amount")
    def _amount(cls, value):
        return _num(value)

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)

    @field_validator("processed_at")
    def _proc(cls, value):
        return _iso(value)


# ---------------------------------------------------------------------------
# Notifications / audit
# ---------------------------------------------------------------------------


class NotificationSerializer(Serializer):
    id: int
    kind: str
    title_key: str
    body_key: str
    params: dict
    link: str = ""
    action: str = ""
    read: bool = field(source="is_read", default=False)
    created_at: str

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)


class AuditSerializer(Serializer):
    id: int
    action: str
    entity: str
    entity_id: str
    summary: str
    actor: UserBriefSerializer | None = None
    created_at: str

    @field_validator("created_at")
    def _create(cls, value):
        return _iso(value)


# ---------------------------------------------------------------------------
# Handlers: dict-returning coroutines (same shapes as the old plain dicts)
# ---------------------------------------------------------------------------


def _hop_loaded(obj, name):
    """True when ``name``'s related object is actually cached on ``obj``."""
    state = getattr(obj, "_state", None)
    cache = getattr(state, "fields_cache", {}) if state is not None else {}
    for key in (name, f"{name}_id"):
        if key in cache:
            return True
    return name in obj.__dict__


def _hop_value(obj, name):
    state = getattr(obj, "_state", None)
    cache = getattr(state, "fields_cache", {}) if state is not None else {}
    for key in (name, f"{name}_id"):
        if key in cache:
            return cache[key]
    return obj.__dict__.get(name)


def _needs_plan_reload(instance, plan) -> bool:
    """True when the serializer's loading plan needs relations/annotations that
    aren't cached on ``instance`` yet.

    ``afrom_model`` lazy-loads *declared* nested relations through the async
    ORM, but it cannot see model-level Python properties that dereference an
    FK (e.g. ``Payment.property_title`` reads ``self.property``).  Those need
    the real relations preloaded, which ``afrom_models`` does via the plan.
    Every hop of every ``select_related`` path is walked so a partially loaded
    chain (e.g. a refund whose ``payment`` object is cached but whose
    ``payment.property`` is not) is still reloaded.
    """
    if not plan:
        return False
    for lookup in plan.select_related:
        cur = instance
        for part in lookup.split("__"):
            if cur is None:
                break
            if not _hop_loaded(cur, part):
                return True
            cur = _hop_value(cur, part)
    for name in plan.annotations:
        if name not in instance.__dict__:
            return True
    return False


async def _adump(cls: type[Serializer], instance, extra: dict | None) -> dict | None:
    if instance is None:
        return None
    plan = cls.loading_plan(instance.__class__)
    if _needs_plan_reload(instance, plan):
        instance = (await cls.afrom_models(instance.__class__._default_manager.filter(pk=instance.pk)))[0]
    serializer = await cls.afrom_model(instance)
    data = serializer.dump()
    if extra:
        data.update(extra)
    return data


async def user_brief(user) -> dict | None:
    return await _adump(UserBriefSerializer, user, None)


async def user(user) -> dict:
    return await _adump(UserSerializer, user, None)


async def property(prop, **extra) -> dict:
    return await _adump(PropertySerializer, prop, extra or None)


async def booking(item, **extra) -> dict:
    return await _adump(BookingSerializer, item, extra or None)


async def payment(item, **extra) -> dict:
    return await _adump(PaymentSerializer, item, extra or None)


async def refund(item, **extra) -> dict:
    return await _adump(RefundSerializer, item, extra or None)


async def notification(item) -> dict:
    return await _adump(NotificationSerializer, item, None)


async def audit(item) -> dict:
    return await _adump(AuditSerializer, item, None)


__all__ = [
    "AuditSerializer",
    "BookingSerializer",
    "NotificationSerializer",
    "PaymentSerializer",
    "PropertySerializer",
    "RefundSerializer",
    "UserBriefSerializer",
    "UserSerializer",
    "audit",
    "booking",
    "notification",
    "payment",
    "property",
    "refund",
    "user",
    "user_brief",
]
