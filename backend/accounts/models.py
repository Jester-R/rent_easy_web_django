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
    commission_rates = models.JSONField(default=dict, blank=True)
    commission_rates_updated_at = models.DateTimeField(null=True, blank=True)
    payment_method_details = models.JSONField(default=dict, blank=True)
    aba_payway_merchant_id = models.CharField(max_length=30, blank=True)
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
        extra.setdefault("is_email_verified", True)
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
    google_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True, db_index=True
    )
    # Telegram user id captured during sign-in (kept separate from the
    # notification chat link so unlinking notifications does not break sign-in).
    telegram_id = models.CharField(
        max_length=64, blank=True, null=True, unique=True, db_index=True
    )
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
    is_email_verified = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_at = models.DateTimeField(null=True, blank=True)

    # Owner payout account (shown only to the owner and superadmins).
    payout_method = models.CharField(
        max_length=16, choices=PayoutMethod.choices, blank=True
    )
    payout_accounts = models.JSONField(default=dict, blank=True)
    payout_account_name = models.CharField(max_length=120, blank=True)
    payout_account_number = models.CharField(max_length=64, blank=True)
    payout_bank_name = models.CharField(max_length=120, blank=True)
    payout_phone = models.CharField(max_length=32, blank=True)
    payout_note = models.CharField(max_length=255, blank=True)
    payout_updated_at = models.DateTimeField(null=True, blank=True)

    # Renter's ABA details used as their saved payment profile.
    payment_account_name = models.CharField(max_length=120, blank=True)
    payment_account_number = models.CharField(max_length=64, blank=True)
    payment_phone = models.CharField(max_length=32, blank=True)

    # Telegram is linked through a short-lived bot deep-link token.
    telegram_chat_id = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    telegram_link_token = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    telegram_link_expires_at = models.DateTimeField(null=True, blank=True)

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
    def telegram_connected(self) -> bool:
        return bool(self.telegram_chat_id)

    @property
    def is_pending_approval(self) -> bool:
        return self.approval_status == ApprovalStatus.PENDING

    @property
    def is_rejected(self) -> bool:
        return self.approval_status == ApprovalStatus.REJECTED

    @property
    def has_payout_details(self) -> bool:
        """A payout can only be sent when the owner supplied the essentials."""
        account = self.get_payout_account()
        return bool(
            self.payout_method
            and account["account_name"].strip()
            and account["account_number"].strip()
        )

    def get_payout_account(self, method: str | None = None) -> dict[str, str]:
        method = method or self.payout_method
        accounts = (
            self.payout_accounts if isinstance(self.payout_accounts, dict) else {}
        )
        account = accounts.get(method) if method else None
        if isinstance(account, dict):
            return {
                "account_name": str(account.get("account_name") or ""),
                "account_number": str(account.get("account_number") or ""),
                "bank_name": str(account.get("bank_name") or ""),
                "phone": str(account.get("phone") or ""),
                "note": str(account.get("note") or ""),
            }
        if accounts:
            return {
                "account_name": "",
                "account_number": "",
                "bank_name": "",
                "phone": "",
                "note": "",
            }
        if method and method == self.payout_method:
            return {
                "account_name": self.payout_account_name,
                "account_number": self.payout_account_number,
                "bank_name": self.payout_bank_name,
                "phone": self.payout_phone,
                "note": self.payout_note,
            }
        return {
            "account_name": "",
            "account_number": "",
            "bank_name": "",
            "phone": "",
            "note": "",
        }

    @property
    def home_url(self) -> str:
        if self.is_superadmin_role:
            return "/console"
        if self.is_owner:
            return "/owner"
        return "/rent"

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


class EmailVerification(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register", "Register"
        LOGIN = "login", "Login"
        PASSWORD_RESET = "password_reset", "Password reset"

    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=32, choices=Purpose.choices, default=Purpose.REGISTER
    )
    payload = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "code", "purpose"]),
            models.Index(fields=["expires_at", "is_verified"]),
        ]

    def __str__(self) -> str:
        return f"OTP({self.email}, {self.purpose}, code={self.code})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class TelegramLoginRequest(models.Model):
    """Short-lived browser request that waits for a Telegram bot ``/start``.

    The website creates a request and opens ``https://t.me/<bot>?start=<token>``.
    When the bot receives that token it stores the Telegram profile here and
    replies with a one-time login code. The browser submits the code to finish
    signing in.
    """

    token = models.CharField(max_length=64, unique=True, db_index=True)
    code = models.CharField(max_length=6, blank=True, default="", db_index=True)
    role = models.CharField(max_length=16, blank=True, default="")
    telegram_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    username = models.CharField(max_length=64, blank=True, default="")
    first_name = models.CharField(max_length=120, blank=True, default="")
    last_name = models.CharField(max_length=120, blank=True, default="")
    photo_url = models.CharField(max_length=500, blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["expires_at", "consumed_at"])]

    def __str__(self) -> str:
        return f"TelegramLoginRequest({self.token[:8]}...)"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


def normalize_identity(value: str) -> str:
    return (value or "").strip().lower()


USERNAME_RE = re.compile(r"^[A-Za-z0-9._\-]{3,30}$")


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.match(value or ""))
