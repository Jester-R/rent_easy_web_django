from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

from .models import USERNAME_VALIDATOR, Role, User, is_valid_username, normalize_identity


class _TemplatedFormMixin:
    """Renders field errors through the bilingual catalogue."""

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    error_key_map = {
        "required": None,
        "invalid_email": "valid_email",
        "email_required": "email_required",
        "username_invalid": "username_rule",
        "password_mismatch": "passwords_dont_match",
        "email_taken": "email_taken",
        "password_too_short": "password_too_short",
        "password_too_common": "password_too_common",
        "password_too_similar": "password_too_similar",
        "password_numeric": "password_numeric",
        "credentials_invalid": "invalid_credentials",
        "inactive": "not_authorized",
        "role_invalid": "select_role_hint",
    }

    def add_key_error(self, field, key):
        self.add_error(field, self.error_key_map.get(key, key) or "invalid")

    def error_messages_for(self, field):
        out = []
        for err in self.errors.get(field, []):
            key = err.code if err.code in self.error_key_map else err.code
            if key in ("required",):
                label = self.fields[field].label if field in self.fields else ""
                out.append(f"field_required:field={label}")
            else:
                out.append(self.error_key_map.get(key, key))
        return out


class LoginForm(_TemplatedFormMixin, forms.Form):
    identifier = forms.CharField(
        max_length=254,
        label="Email or Username",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autofocus": "autocapitalize=off",
                "spellcheck": "false",
                "placeholder": "Enter email or username",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "required": {"identifier": "email_or_username_required", "password": "field_required:field=Password"},
    }

    def clean_identifier(self):
        value = normalize_identity(self.cleaned_data["identifier"])
        if not value:
            raise ValidationError("email_or_username_required", code="required")
        return value

    def clean(self):
        cleaned = super().clean()
        identifier = cleaned.get("identifier")
        password = cleaned.get("password")
        if identifier and password:
            user = authenticate(self.request, username=identifier, password=password)
            if user is None:
                user = User.objects.filter(email=identifier).first() or User.objects.filter(
                    username=identifier
                ).first()
                if user is None:
                    raise ValidationError("credentials_invalid", code="credentials_invalid")
                if not user.check_password(password):
                    raise ValidationError("credentials_invalid", code="credentials_invalid")
                if not user.is_active:
                    raise ValidationError("inactive", code="inactive")
            cleaned["user"] = user
        return cleaned

    def get_user(self):
        return self.cleaned_data.get("user")


class RegisterForm(_TemplatedFormMixin, forms.Form):
    full_name = forms.CharField(
        max_length=120,
        label="Full Name",
        widget=forms.TextInput(attrs={"placeholder": "Full Name", "autocapitalize": "words"}),
    )
    username = forms.CharField(
        max_length=30,
        label="Username",
        validators=[USERNAME_VALIDATOR],
        widget=forms.TextInput(attrs={"placeholder": "Username", "autocomplete": "username"}),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"placeholder": "Email", "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    error_messages = {
        "required": {
            "full_name": "field_required:field=Full Name",
            "username": "username_required",
            "email": "email_required",
            "password": "field_required:field=Password",
            "password_confirm": "field_required:field=Confirm Password",
        }
    }

    def clean_username(self):
        value = (self.cleaned_data.get("username") or "").strip()
        if not is_valid_username(value):
            raise ValidationError("username_invalid", code="username_invalid")
        if User.objects.filter(username__iexact=value).exists():
            raise ValidationError("email_taken", code="email_taken")
        return value

    def clean_email(self):
        value = normalize_identity(self.cleaned_data.get("email"))
        if not value:
            raise ValidationError("email_required", code="required")
        if User.objects.filter(email__iexact=value).exists():
            raise ValidationError("email_taken", code="email_taken")
        return value

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("password_confirm")
        if password and confirm and password != confirm:
            self.add_error("password_confirm", "password_mismatch")
        return cleaned

    def save(self) -> User:
        data = self.cleaned_data
        return User.objects.create_user(
            email=data["email"],
            username=data["username"],
            password=data["password"],
            full_name=data["full_name"],
            role=Role.RENTER,
        )


class RoleSelectForm(forms.Form):
    ROLE_CHOICES = [(Role.RENTER, "renter"), (Role.OWNER, "owner")]

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="Role",
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": "select_role_hint", "required": "select_role_hint"},
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean_role(self):
        value = self.cleaned_data.get("role")
        if value not in dict(self.ROLE_CHOICES):
            raise ValidationError("select_role_hint", code="role_invalid")
        return value


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "email", "username"]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Full Name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
        }

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-input")

    def clean_email(self):
        value = normalize_identity(self.cleaned_data.get("email"))
        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("email_taken", code="email_taken")
        return value

    def clean_username(self):
        value = (self.cleaned_data.get("username") or "").strip()
        if not is_valid_username(value):
            raise ValidationError("username_invalid", code="username_invalid")
        qs = User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("email_taken", code="email_taken")
        return value


class AdminUserForm(forms.ModelForm):
    """Superadmin console user editor (create + edit)."""

    password = forms.CharField(
        required=False,
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Leave blank to keep current password",
    )
    role = forms.ChoiceField(choices=Role.choices, label="Role")

    class Meta:
        model = User
        fields = ["full_name", "username", "email", "role", "is_active"]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Full Name"}),
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "role": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = False
        self.fields["role"].required = True

    def clean_email(self):
        value = normalize_identity(self.cleaned_data.get("email"))
        if not value:
            raise ValidationError("email_required", code="required")
        qs = User.objects.filter(email__iexact=value)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("email_taken", code="email_taken")
        return value

    def clean_username(self):
        value = (self.cleaned_data.get("username") or "").strip()
        if not is_valid_username(value):
            raise ValidationError("username_invalid", code="username_invalid")
        qs = User.objects.filter(username__iexact=value)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("email_taken", code="email_taken")
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password") or ""
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
