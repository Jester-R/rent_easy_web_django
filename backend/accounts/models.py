from __future__ import annotations

import re

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

USERNAME_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-z0-9._\-]{3,30}$",
    message="Use 3-30 chars: letters, numbers, ., _, -",
)


class Role(models.TextChoices):
    RENTER = "renter", "Renter"
    OWNER = "owner", "Property Owner"
    SUPERADMIN = "superadmin", "Super Admin"


class ApprovalStatus(models.TextChoices):
    """Owner accounts need a superadmin to approve them before first login."""

    APPROVED = "approved", "Approved"
    PENDING = "pending", "Pending approval"
    REJECTED = "rejected", "Rejected"


ROLE_VALUES = {value for value, _ in Role.choices}
APPROVAL_VALUES = {value for value, _ in ApprovalStatus.choices}


class PayoutMethod(models.TextChoices):
    """Where an owner wants the platform to send collected rent."""

    ABA = "aba", "ABA Bank"
    WING = "wing", "Wing Bank"
    ACLEDA = "acleda", "ACLEDA Bank"
    OTHER = "other", "Other"


PAYOUT_METHOD_VALUES = {value for value, _ in PayoutMethod.choices}


class PlatformSettings(models.Model):
    """Singleton row holding platform-wide switches controlled by superadmins."""

    auto_approve_owners = models.BooleanField(
        default=False,
        help_text="When enabled, new property owners are approved automatically.",
    )
    property_categories = models.JSONField(default=list, blank=True)
    notification_messages = models.JSONField(default=dict, blank=True)
    home_promotion = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform settings"
        verbose_name_plural = "Platform settings"

    def __str__(self) -> str:
        return "Platform settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "PlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(
        self, email, username, password, full_name="", role=Role.RENTER, **extra
    ):
        if not email:
            raise ValueError("Users must have an email address")
        if not username:
            raise ValueError("Users must have a username")
        email = self.normalize_email(email).strip().lower()
        username = username.strip()
        role = role if role in ROLE_VALUES else Role.RENTER
        extra.setdefault("approval_status", ApprovalStatus.APPROVED)
        user = self.model(
            email=email,
            username=username,
            full_name=(full_name or "").strip(),
            role=role,
            **extra,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username="", password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        username = username or email.split("@")[0]
        return self._create_user(email, username, password, **extra)

    def create_superuser(self, email, username="", password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.SUPERADMIN)
        extra.setdefault("full_name", username or email)
        if extra["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        username = username or email.split("@")[0]
        return self._create_user(email, username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=254)
    username = models.CharField(
        max_length=30, unique=True, validators=[USERNAME_VALIDATOR]
    )
    full_name = models.CharField(max_length=120, blank=True)
    # Supports either an external avatar URL or a small uploaded image data URL.
    avatar_url = models.TextField(blank=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.RENTER, db_index=True
    )
    approval_status = models.CharField(
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_at = models.DateTimeField(null=True, blank=True)

    # Owner payout account (shown only to the owner and superadmins).
    payout_method = models.CharField(
        max_length=16, choices=PayoutMethod.choices, blank=True
    )
    payout_account_name = models.CharField(max_length=120, blank=True)
    payout_account_number = models.CharField(max_length=64, blank=True)
    payout_bank_name = models.CharField(max_length=120, blank=True)
    payout_phone = models.CharField(max_length=32, blank=True)
    payout_note = models.CharField(max_length=255, blank=True)
    payout_updated_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["full_name", "email"]
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return f"{self.display_name} <{self.email}>"

    # -- helpers ---------------------------------------------------------
    @property
    def display_name(self) -> str:
        return self.full_name.strip() or self.username or self.email

    @property
    def is_renter(self) -> bool:
        return self.role == Role.RENTER

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_superadmin_role(self) -> bool:
        return self.role == Role.SUPERADMIN

    @property
    def is_pending_approval(self) -> bool:
        return self.approval_status == ApprovalStatus.PENDING

    @property
    def is_rejected(self) -> bool:
        return self.approval_status == ApprovalStatus.REJECTED

    @property
    def has_payout_details(self) -> bool:
        """A payout can only be sent when the owner supplied the essentials."""
        return bool(
            self.payout_method
            and self.payout_account_name.strip()
            and self.payout_account_number.strip()
        )

    @property
    def home_url(self) -> str:
        if self.is_superadmin_role:
            return "/console/"
        if self.is_owner:
            return "/owner/"
        return "/rent/"

    @property
    def avatar_hue(self) -> int:
        """Deterministic hue from the email so avatars stay stable across pages."""
        digest = sum(ord(c) for c in self.email)
        return (digest * 37) % 360

    def get_short_name(self) -> str:
        return self.display_name

    def get_full_name(self) -> str:
        return self.display_name

    def natural_key(self):
        return (self.email,)

    def touch_login(self) -> None:
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at"])


class AuditLog(models.Model):
    """Lightweight trail of privileged actions (superadmin console)."""

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        STATUS = "status", "Status change"
        PAYMENT = "payment", "Payment"
        PAYOUT = "payout", "Payout"
        REFUND = "refund", "Refund"

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    entity = models.CharField(max_length=32)
    entity_id = models.CharField(max_length=64, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.action}:{self.entity}:{self.entity_id}"


def normalize_identity(value: str) -> str:
    return (value or "").strip().lower()


USERNAME_RE = re.compile(r"^[A-Za-z0-9._\-]{3,30}$")


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.match(value or ""))
