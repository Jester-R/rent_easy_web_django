from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from core.decorators import require_http_methods_
from core.middleware import persist_language

from .forms import LoginForm, RegisterForm, RoleSelectForm, UserProfileForm
from .models import AuditLog, Role, User


@never_cache
@require_http_methods_(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.home_url)

    if request.method == "POST":
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["identifier"],
                password=form.cleaned_data["password"],
            )
            if user is None:
                form.add_error(None, "invalid_credentials")
            elif not user.is_active:
                form.add_error(None, "not_authorized")
            else:
                login(request, user)
                user.touch_login()
                destination = request.POST.get("next") or request.GET.get("next") or user.home_url
                if not destination.startswith("/"):
                    destination = user.home_url
                return redirect(destination)
    else:
        form = LoginForm(request=request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@never_cache
@require_http_methods_(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.home_url)

    if request.method == "POST":
        form = RegisterForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.save()
            request.session["renteasy_pending_role_user"] = str(user.pk)
            return redirect(reverse("role_select"))
    else:
        form = RegisterForm(request=request)

    return render(request, "accounts/register.html", {"form": form})


@never_cache
@require_http_methods_(["GET", "POST"])
def role_select_view(request):
    pending_id = request.session.get("renteasy_pending_role_user")
    if not pending_id:
        return redirect(reverse("register"))
    user = User.objects.filter(pk=pending_id).first()
    if user is None:
        request.session.pop("renteasy_pending_role_user", None)
        return redirect(reverse("register"))

    if request.method == "POST":
        form = RoleSelectForm(request=request, data=request.POST)
        if form.is_valid():
            user.role = form.cleaned_data["role"]
            user.save(update_fields=["role"])
            AuditLog.objects.create(
                actor=user,
                action=AuditLog.Action.UPDATE,
                entity="user",
                entity_id=str(user.pk),
                summary=f"role set to {user.role}",
            )
            request.session.pop("renteasy_pending_role_user", None)
            request.session["renteasy_flash"] = "registration_complete"
            return redirect(reverse("login"))
    else:
        form = RoleSelectForm(request=request)

    return render(request, "accounts/role_select.html", {"form": form, "pending_user": user})


@never_cache
@require_http_methods_(["POST"])
def logout_view(request):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=AuditLog.Action.UPDATE,
        entity="session",
        entity_id=str(request.user.pk) if request.user.is_authenticated else "",
        summary="logout",
    )
    logout(request)
    return redirect(reverse("login"))


@never_cache
@login_required
@require_http_methods_(["GET", "POST"])
def profile_view(request):
    """Shared profile + preferences page for every role."""
    form = UserProfileForm(
        request=request,
        data=request.POST if request.method == "POST" else None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        request.session["renteasy_flash"] = "account_updated"
        return redirect(request.user.home_url)
    return render(request, "accounts/profile.html", {"form": form})


renter_required = user_passes_test(
    lambda u: u.is_authenticated and u.is_renter,
    login_url="login",
    redirect_field_name=None,
)
owner_required = user_passes_test(
    lambda u: u.is_authenticated and u.is_owner,
    login_url="login",
    redirect_field_name=None,
)
superadmin_required = user_passes_test(
    lambda u: u.is_authenticated and u.is_superadmin_role,
    login_url="login",
    redirect_field_name=None,
)


def deny(request):
    """Rendered when a signed-in user hits a portal they do not own."""
    return render(
        request,
        "accounts/denied.html",
        {"required_role": request.GET.get("role", "")},
        status=403,
    )


def home_router(request):
    """Entry point that routes by role (or to login / landing)."""
    if request.user.is_authenticated:
        return redirect(request.user.home_url)
    return redirect("landing")


@never_cache
def set_language_view(request):
    from core.i18n import SUPPORTED_LANGUAGE_CODES

    code = (request.POST.get("lang") or request.GET.get("lang") or "").strip()[:2]
    target = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not target.startswith("/"):
        target = "/"
    response = redirect(target)
    if code in SUPPORTED_LANGUAGE_CODES:
        persist_language(request, code, response)
    return response


@never_cache
def set_theme_view(request):
    from core.middleware import THEMES, persist_theme

    theme = (request.POST.get("theme") or request.GET.get("theme") or "").strip().lower()
    target = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not target.startswith("/"):
        target = "/"
    response = redirect(target)
    if theme in THEMES:
        persist_theme(request, theme, response)
    return response


def _search_users(query: str):
    return User.objects.filter(
        Q(email__icontains=query) | Q(username__icontains=query) | Q(full_name__icontains=query)
    )
