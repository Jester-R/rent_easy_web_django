from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required  # noqa: F401
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bookings.helpers import (
    BookingAdminForm,
    BookingCreateAdminForm,
    apply_status_filter,
    booking_all_queryset,
    get_booking_for,
    redirect_back,
    search_bookings,
)
from bookings.models import Booking, BookingStatus
from core.i18n import Translator
from listings.forms import PropertyForm
from listings.models import Favorite, Property
from payments.views import PaymentAdminForm, PaymentCreateAdminForm
from payments.models import Payment, Refund
from payments.services import process_refund

from .forms import AdminUserForm
from .models import AuditLog, Role, User
from .views import superadmin_required

# Every /console/ endpoint is superadmin-only.
console_required = superadmin_required


def audit(actor, action: str, entity: str, entity_id, summary: str = "") -> None:
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        summary=summary[:255],
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@console_required
def dashboard(request):
    users_qs = User.objects.all()
    properties_qs = Property.objects.all()
    bookings_qs = Booking.objects.all()
    payments_qs = Payment.objects.all()

    revenue = payments_qs.filter(status=Payment.Status.SUCCESS).aggregate(v=Sum("amount"))["v"] or 0
    refunded = payments_qs.aggregate(v=Sum("refunded_amount"))["v"] or 0
    avg_rent = properties_qs.aggregate(v=Avg("price_per_month"))["v"] or 0

    monthly_rows = list(
        payments_qs.filter(status=Payment.Status.SUCCESS)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("month")
    )
    max_total = max((float(row["total"]) for row in monthly_rows), default=0.0) or 1.0

    top_properties = (
        properties_qs.annotate(
            revenue=Sum(
                "payments__amount",
                filter=Q(payments__status=Payment.Status.SUCCESS),
            ),
            bookings_total=Count("bookings", distinct=True),
            favorites_total=Count("favorites", distinct=True),
        )
        .order_by("-revenue")[:6]
    )

    role_breakdown = list(users_qs.values("role").annotate(n=Count("id")).order_by("-n"))
    recent_bookings = Booking.objects.select_related("property", "renter", "owner").order_by("-created_at")[:8]
    recent_users = users_qs.order_by("-date_joined")[:6]

    status_counts = {row["status"]: row["n"] for row in bookings_qs.values("status").annotate(n=Count("id"))}

    t: Translator = getattr(request, "translator", None) or Translator("en")
    funnel_rows = [
        (t("status_pending"), status_counts.get(BookingStatus.PENDING, 0), "bg-warning", "pending"),
        (t("status_approved"), status_counts.get(BookingStatus.APPROVED, 0), "bg-primary", "approved"),
        (t("status_rejected"), status_counts.get(BookingStatus.REJECTED, 0), "bg-danger", "rejected"),
        (t("status_cancelled"), status_counts.get(BookingStatus.CANCELLED, 0), "bg-ink-3", "cancelled"),
    ]

    return render(
        request,
        "console/dashboard.html",
        {
            "stats": {
                "users": users_qs.count(),
                "owners": users_qs.filter(role=Role.OWNER).count(),
                "renters": users_qs.filter(role=Role.RENTER).count(),
                "properties": properties_qs.count(),
                "bookings": bookings_qs.count(),
                "payments": payments_qs.count(),
                "favorites": Favorite.objects.count(),
                "refunds": Refund.objects.count(),
                "pending_refunds": Refund.objects.filter(status=Refund.Status.PENDING).count(),
                "revenue": float(revenue),
                "refunded": float(refunded),
                "avg_rent": float(avg_rent),
            },
            "status_counts": status_counts,
            "pending_count": status_counts.get(BookingStatus.PENDING, 0),
            "approved_count": status_counts.get(BookingStatus.APPROVED, 0),
            "rejected_count": status_counts.get(BookingStatus.REJECTED, 0),
            "cancelled_count": status_counts.get(BookingStatus.CANCELLED, 0),
            "monthly_rows": monthly_rows,
            "max_total": max_total,
            "top_properties": top_properties,
            "role_breakdown": role_breakdown,
            "recent_bookings": recent_bookings,
            "recent_users": recent_users,
            "audit_logs": AuditLog.objects.select_related("actor")[:8],
            "funnel_rows": funnel_rows,
        },
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@console_required
def users_list(request):
    query = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "all").strip()
    queryset = User.objects.all().order_by("-date_joined")
    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query) | Q(username__icontains=query)
        )
    if role in dict(Role.choices):
        queryset = queryset.filter(role=role)
    users = list(queryset.annotate(property_count=Count("properties", distinct=True), booking_count=Count("renters_bookings", distinct=True)))
    return render(
        request,
        "console/users.html",
        {"users": users, "query": query, "role": role, "roles": Role.choices, "total": User.objects.count()},
    )


@console_required
def user_create(request):
    if request.method == "POST":
        form = AdminUserForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data.get("password") or ""
            if not password:
                form.add_error("password", "password_too_short")
            else:
                user = form.save(commit=False)
                user.set_password(password)
                user.save()
                audit(request.user, AuditLog.Action.CREATE, "user", user.pk, f"created {user.email}")
                request.session["renteasy_flash"] = "account_created"
                return redirect("console:users")
    else:
        form = AdminUserForm(initial={"role": Role.RENTER, "is_active": True})
    return render(request, "console/user_form.html", {"form": form, "mode": "create"})


@console_required
def user_edit(request, pk: int):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = AdminUserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            audit(request.user, AuditLog.Action.UPDATE, "user", user_obj.pk, f"updated {user_obj.email}")
            request.session["renteasy_flash"] = "account_updated"
            return redirect("console:users")
    else:
        form = AdminUserForm(instance=user_obj)
    return render(request, "console/user_form.html", {"form": form, "mode": "edit", "user_obj": user_obj})


@require_POST
@console_required
def user_delete(request, pk: int):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj.pk == request.user.pk:
        request.session["renteasy_flash"] = "not_authorized"
        return redirect("console:users")
    label = user_obj.email
    user_obj.delete()
    audit(request.user, AuditLog.Action.DELETE, "user", pk, f"deleted {label}")
    request.session["renteasy_flash"] = "record_deleted"
    return redirect_back(request, "console:users")


@require_POST
@console_required
def users_bulk_delete(request):
    ids = [int(i) for i in request.POST.getlist("ids") if str(i).isdigit()]
    deleted = 0
    for user_id in ids:
        if user_id == request.user.pk:
            continue
        if User.objects.filter(pk=user_id).delete()[0]:
            deleted += 1
    audit(request.user, AuditLog.Action.DELETE, "user", ",".join(map(str, ids)), f"bulk deleted {deleted}")
    request.session["renteasy_flash"] = "records_deleted"
    return redirect_back(request, "console:users")


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@console_required
def properties_list(request):
    query = (request.GET.get("q") or "").strip()
    owner = (request.GET.get("owner") or "").strip()
    queryset = Property.objects.select_related("owner").order_by("-created_at")
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) | Q(location__icontains=query) | Q(owner__email__icontains=query)
        )
    if owner:
        queryset = queryset.filter(owner_id=owner)
    properties = list(
        queryset.annotate(
            favorite_count=Count("favorites", distinct=True),
            booking_count=Count("bookings", distinct=True),
        )
    )
    return render(
        request,
        "console/properties.html",
        {
            "properties": properties,
            "query": query,
            "owner": owner,
            "owners": User.objects.filter(role=Role.OWNER).order_by("full_name"),
            "total": Property.objects.count(),
        },
    )


@console_required
def property_create(request):
    owners = User.objects.filter(role=Role.OWNER).order_by("full_name", "email")
    if request.method == "POST":
        form = PropertyForm(request.POST)
        owner_id = request.POST.get("owner") or ""
        owner = User.objects.filter(pk=owner_id, role=Role.OWNER).first()
        if form.is_valid() and owner:
            property_obj = form.save(commit=False)
            property_obj.owner = owner
            property_obj.save()
            audit(request.user, AuditLog.Action.CREATE, "property", property_obj.pk, f"created {property_obj.title}")
            request.session["renteasy_flash"] = "property_created"
            return redirect("console:properties")
        if owner is None:
            form.add_error(None, "owner_required")
    else:
        form = PropertyForm()
    return render(
        request,
        "console/property_form.html",
        {"form": form, "mode": "create", "owners": owners, "selected_owner": request.POST.get("owner", "")},
    )


@console_required
def property_edit(request, pk: int):
    property_obj = get_object_or_404(Property, pk=pk)
    owners = User.objects.filter(role=Role.OWNER).order_by("full_name", "email")
    if request.method == "POST":
        form = PropertyForm(request.POST, instance=property_obj)
        owner_id = request.POST.get("owner") or ""
        owner = User.objects.filter(pk=owner_id, role=Role.OWNER).first() or property_obj.owner
        if form.is_valid() and owner:
            form.save()
            property_obj.owner = owner
            property_obj.save(update_fields=["owner"])
            audit(request.user, AuditLog.Action.UPDATE, "property", property_obj.pk, f"updated {property_obj.title}")
            request.session["renteasy_flash"] = "property_updated"
            return redirect("console:properties")
    else:
        form = PropertyForm(instance=property_obj)
    return render(
        request,
        "console/property_form.html",
        {
            "form": form,
            "mode": "edit",
            "property": property_obj,
            "owners": owners,
            "selected_owner": str(property_obj.owner_id),
        },
    )


@require_POST
@console_required
def properties_bulk_delete(request):
    ids = [int(i) for i in request.POST.getlist("ids") if str(i).isdigit()]
    count, _ = Property.objects.filter(pk__in=ids).delete()
    audit(request.user, AuditLog.Action.DELETE, "property", ",".join(map(str, ids)), "bulk deleted properties")
    request.session["renteasy_flash"] = "records_deleted"
    return redirect_back(request, "console:properties")


@require_POST
@console_required
def property_delete(request, pk: int):
    property_obj = get_object_or_404(Property, pk=pk)
    title = property_obj.title
    property_obj.delete()
    audit(request.user, AuditLog.Action.DELETE, "property", pk, f"deleted {title}")
    request.session["renteasy_flash"] = "record_deleted"
    return redirect_back(request, "console:properties")


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


@console_required
def bookings_list(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    queryset = apply_status_filter(booking_all_queryset(), status)
    queryset = search_bookings(queryset, query)
    bookings = list(queryset)
    status_counts = {"all": Booking.objects.count()}
    for row in Booking.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    return render(
        request,
        "console/bookings.html",
        {
            "bookings": bookings,
            "query": query,
            "status": status,
            "statuses": BookingStatus.choices,
            "status_counts": status_counts,
            "total": Booking.objects.count(),
        },
    )


@console_required
def booking_create(request):
    properties = Property.objects.select_related("owner").order_by("title")
    renters = User.objects.filter(role=Role.RENTER).order_by("full_name", "email")
    if request.method == "POST":
        form = BookingCreateAdminForm(request.POST)
        if form.is_valid():
            booking = form.save()
            audit(request.user, AuditLog.Action.CREATE, "booking", booking.pk, f"created {booking.reference}")
            request.session["renteasy_flash"] = "booking_created"
            return redirect("console:bookings")
    else:
        form = BookingCreateAdminForm(initial={"status": BookingStatus.PENDING, "lease_months": 12})
    return render(
        request,
        "console/booking_form.html",
        {"form": form, "mode": "create", "properties": properties, "renters": renters},
    )


@console_required
def booking_edit(request, pk: int):
    booking = get_booking_for(pk)
    if request.method == "POST":
        form = BookingAdminForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            audit(request.user, AuditLog.Action.UPDATE, "booking", booking.pk, f"updated {booking.reference}")
            request.session["renteasy_flash"] = "booking_updated"
            return redirect("console:bookings")
    else:
        form = BookingAdminForm(instance=booking)
    return render(request, "console/booking_form.html", {"form": form, "mode": "edit", "booking": booking})


@require_POST
@console_required
def bookings_bulk_delete(request):
    ids = [int(i) for i in request.POST.getlist("ids") if str(i).isdigit()]
    Booking.objects.filter(pk__in=ids).delete()
    audit(request.user, AuditLog.Action.DELETE, "booking", ",".join(map(str, ids)), "bulk deleted bookings")
    request.session["renteasy_flash"] = "records_deleted"
    return redirect_back(request, "console:bookings")


@require_POST
@console_required
def booking_delete(request, pk: int):
    booking = get_booking_for(pk)
    ref = booking.reference
    booking.delete()
    audit(request.user, AuditLog.Action.DELETE, "booking", pk, f"deleted {ref}")
    request.session["renteasy_flash"] = "record_deleted"
    return redirect_back(request, "console:bookings")


# ---------------------------------------------------------------------------
# Payments & refunds
# ---------------------------------------------------------------------------


@console_required
def payments_list(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    queryset = Payment.objects.select_related("property", "user", "booking").order_by("-created_at")
    if query:
        queryset = queryset.filter(
            Q(reference__icontains=query) | Q(property__title__icontains=query) | Q(user__email__icontains=query)
        )
    if status in Payment.Status.values:
        queryset = queryset.filter(status=status)
    elif status == "Refunded":
        queryset = queryset.filter(refund_status=Payment.RefundStatus.PROCESSED)
    status_counts = {"all": Payment.objects.count()}
    for row in Payment.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    status_counts["Refunded"] = Payment.objects.filter(refund_status=Payment.RefundStatus.PROCESSED).count()

    return render(
        request,
        "console/payments.html",
        {
            "payments": list(queryset),
            "query": query,
            "status": status,
            "statuses": list(Payment.Status.choices) + [("Refunded", "Refunded")],
            "status_counts": status_counts,
            "total": Payment.objects.count(),
            "revenue": float(Payment.objects.filter(status=Payment.Status.SUCCESS).aggregate(v=Sum("amount"))["v"] or 0),
            "refunds": Refund.objects.select_related("payment", "booking")[:10],
        },
    )


@console_required
def payment_create(request):
    if request.method == "POST":
        form = PaymentCreateAdminForm(request.POST)
        if form.is_valid():
            payment = form.save()
            audit(request.user, AuditLog.Action.CREATE, "payment", payment.pk, f"created {payment.reference}")
            request.session["renteasy_flash"] = "payment_created"
            return redirect("console:payments")
    else:
        form = PaymentCreateAdminForm(initial={"status": Payment.Status.SUCCESS, "method": Payment.Method.ABA})
    return render(request, "console/payment_form.html", {"form": form, "mode": "create"})


@console_required
def payment_edit(request, pk: int):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == "POST":
        form = PaymentAdminForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            audit(request.user, AuditLog.Action.UPDATE, "payment", payment.pk, f"updated {payment.reference}")
            request.session["renteasy_flash"] = "payment_updated"
            return redirect("console:payments")
    else:
        form = PaymentAdminForm(instance=payment)
    return render(request, "console/payment_form.html", {"form": form, "mode": "edit", "payment": payment})


@require_POST
@console_required
def payments_bulk_delete(request):
    ids = [int(i) for i in request.POST.getlist("ids") if str(i).isdigit()]
    Payment.objects.filter(pk__in=ids).delete()
    audit(request.user, AuditLog.Action.DELETE, "payment", ",".join(map(str, ids)), "bulk deleted payments")
    request.session["renteasy_flash"] = "records_deleted"
    return redirect_back(request, "console:payments")


@require_POST
@console_required
def payment_delete(request, pk: int):
    payment = get_object_or_404(Payment, pk=pk)
    ref = payment.reference
    payment.delete()
    audit(request.user, AuditLog.Action.DELETE, "payment", pk, f"deleted {ref}")
    request.session["renteasy_flash"] = "record_deleted"
    return redirect_back(request, "console:payments")


@require_POST
@console_required
def refund_process(request, pk: int):
    refund = get_object_or_404(Refund, pk=pk)
    ok = process_refund(refund, actor=request.user)
    audit(request.user, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    request.session["renteasy_flash"] = "refund_processed" if ok else "not_authorized"
    return redirect("console:payments")


@require_POST
@console_required
def refund_create(request):
    payment_id = request.POST.get("payment")
    payment = get_object_or_404(Payment, pk=payment_id)
    refund = Refund.objects.create(
        payment=payment,
        booking=payment.booking or Booking.objects.filter(payment=payment).first(),
        amount=payment.amount,
        reason=request.POST.get("reason") or Refund.Reason.OTHER,
    )
    audit(request.user, AuditLog.Action.REFUND, "refund", refund.pk, refund.reference)
    request.session["renteasy_flash"] = "refund_created"
    return redirect("console:payments")
