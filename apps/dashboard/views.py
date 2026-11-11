import csv
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, ProtectedError
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.models import AuditLog, SiteSetting
from apps.core.utils import get_client_ip, log_action, notify
from apps.leads.models import Lead, LeadAssignment, LeadStatusHistory, WhatsAppClick
from apps.pages.models import Page
from apps.properties.models import Project, Property, PropertyImage

from .crud import CRUD_BY_SLUG, CRUDS
from .forms import (
    AdminSetPasswordForm,
    DashboardLoginForm,
    LeadAssignForm,
    LeadCreateForm,
    LeadNoteForm,
    LeadUpdateForm,
    PropertyAdminForm,
    PropertyImageUploadForm,
    PropertyReviewForm,
    SiteSettingForm,
    UserForm,
)

User = get_user_model()


# --------------------------------------------------------------------------- access helpers


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def perm_required(*perms):
    """Require staff + ALL listed permissions. Enforced server-side for every sensitive action."""

    def decorator(view):
        @wraps(view)
        @staff_required
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perms(perms):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def _paginate(request, qs, per_page=25):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


# --------------------------------------------------------------------------- authentication


class LoginView(auth_views.LoginView):
    """Login with per-IP + per-username lockout after repeated failures."""

    template_name = "dashboard/login.html"
    authentication_form = DashboardLoginForm
    redirect_authenticated_user = True

    def _keys(self):
        ip = get_client_ip(self.request)
        username = (self.request.POST.get("username") or "").lower()[:150]
        return f"hm:loginfail:ip:{ip}", f"hm:loginfail:user:{username}"

    def post(self, request, *args, **kwargs):
        if any((cache.get(k) or 0) >= settings.LOGIN_FAILURE_LIMIT for k in self._keys()):
            # Do not even attempt authentication while locked out.
            context = self.get_context_data(form=self.form_class(request=request))
            context["lockout_message"] = "Too many failed attempts. Please wait 15 minutes and try again."
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for key in self._keys():
            if not cache.add(key, 1, settings.LOGIN_LOCKOUT_SECONDS):
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete_many(list(self._keys()))
        return super().form_valid(form)


# --------------------------------------------------------------------------- overview


@staff_required
def home(request):
    user = request.user
    today = timezone.localdate()
    ctx = {"today": today}
    if user.has_perm("properties.view_property"):
        props = Property.objects.all()
        ctx["property_stats"] = {
            "active": props.filter(status=Property.Status.PUBLISHED).count(),
            "pending": props.filter(status=Property.Status.PENDING).count(),
            "closed": props.filter(status__in=[Property.Status.SOLD, Property.Status.RENTED]).count(),
            "inactive": props.filter(status__in=[Property.Status.ARCHIVED, Property.Status.DRAFT,
                                                 Property.Status.REJECTED, Property.Status.CORRECTION]).count(),
        }
        ctx["recent_submissions"] = props.filter(source=Property.Source.OWNER).select_related("city")[:6]
    if user.has_perm("leads.view_lead"):
        leads = Lead.objects.visible_to(user)
        ctx["lead_stats"] = {
            "new": leads.filter(status=Lead.Status.NEW).count(),
            "today": leads.filter(created_at__date=today).count(),
            "due": leads.open().filter(next_follow_up__lte=today).count(),
            "open": leads.open().count(),
        }
        ctx["leads_by_status"] = leads.values("status").annotate(n=Count("id")).order_by("-n")
        ctx["status_labels"] = dict(Lead.Status.choices)
        ctx["followups"] = leads.open().filter(next_follow_up__lte=today).select_related("assigned_to").order_by("next_follow_up")[:8]
        ctx["recent_leads"] = leads.select_related("interested_property")[:8]
    if user.has_perm("core.view_auditlog"):
        ctx["recent_activity"] = AuditLog.objects.select_related("actor").exclude(action=AuditLog.Action.LOGIN_FAILED)[:8]
    if user.has_perm("core.change_sitesetting"):
        site = SiteSetting.load()
        checklist = [
            ("Business phone", bool(site.phone)),
            ("WhatsApp number", bool(site.whatsapp_number)),
            ("Business email", bool(site.email)),
            ("Office address", bool(site.address)),
            ("Legal pages reviewed", not Page.objects.filter(is_legal=True, legal_reviewed=False).exists()),
            ("No sample data", not Property.objects.filter(is_sample=True).exists()
             and not Project.objects.filter(is_sample=True).exists()),
        ]
        ctx["launch_checklist"] = checklist
        ctx["launch_ready"] = all(ok for _, ok in checklist)
    return render(request, "dashboard/home.html", ctx)


# --------------------------------------------------------------------------- properties


@perm_required("properties.view_property")
def property_list(request):
    qs = Property.objects.select_related("city", "locality", "property_type", "assigned_to").prefetch_related("images")
    status = request.GET.get("status", "")
    if status in Property.Status.values:
        qs = qs.filter(status=status)
    if (purpose := request.GET.get("purpose", "")) in Property.Purpose.values:
        qs = qs.filter(purpose=purpose)
    if (source := request.GET.get("source", "")) in Property.Source.values:
        qs = qs.filter(source=source)
    if q := request.GET.get("q", "").strip()[:100]:
        qs = qs.filter(Q(title__icontains=q) | Q(listing_id__iexact=q) | Q(owner_phone__icontains=q)
                       | Q(locality__name__icontains=q) | Q(owner_name__icontains=q))
    counts = dict(Property.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "dashboard/property_list.html", {
        "page_obj": _paginate(request, qs.order_by("-updated_at")),
        "statuses": [(v, label, counts.get(v, 0)) for v, label in Property.Status.choices],
        "current_status": status,
        "purposes": Property.Purpose.choices,
        "sources": Property.Source.choices,
    })


def _apply_verification(request, prop, was_verified):
    if prop.is_verified and not was_verified:
        prop.verified_at, prop.verified_by = timezone.now(), request.user
    elif not prop.is_verified:
        prop.verified_at, prop.verified_by = None, None


@perm_required("properties.add_property")
def property_create(request):
    form = PropertyAdminForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        prop = form.save(commit=False)
        prop.created_by = request.user
        prop.source = Property.Source.STAFF
        _apply_verification(request, prop, False)
        prop.save()
        form.save_m2m()
        log_action(request, AuditLog.Action.CREATE, prop, f"Created property {prop.title}")
        messages.success(request, f"Property {prop.listing_id or ''} created. Add photos below.")
        return redirect("dashboard:property_detail", pk=prop.pk)
    return render(request, "dashboard/property_form.html", {"form": form, "title": "Add property"})


@perm_required("properties.change_property")
def property_edit(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    was_verified, old_status = prop.is_verified, prop.status
    form = PropertyAdminForm(request.POST or None, instance=prop, user=request.user)
    if request.method == "POST" and form.is_valid():
        prop = form.save(commit=False)
        _apply_verification(request, prop, was_verified)
        prop.save()
        form.save_m2m()
        changed = ", ".join(form.changed_data)[:250]
        log_action(request, AuditLog.Action.UPDATE, prop, f"Changed: {changed}")
        if old_status != prop.status:
            log_action(request, AuditLog.Action.STATUS, prop, f"{old_status} → {prop.status}")
        messages.success(request, "Property saved.")
        return redirect("dashboard:property_detail", pk=prop.pk)
    return render(request, "dashboard/property_form.html", {"form": form, "property": prop, "title": f"Edit {prop.listing_id}"})


@perm_required("properties.view_property")
def property_detail(request, pk):
    prop = get_object_or_404(
        Property.objects.select_related("city", "locality", "property_type", "assigned_to", "created_by", "verified_by"),
        pk=pk,
    )
    leads = Lead.objects.visible_to(request.user).filter(interested_property=prop)[:10]
    return render(request, "dashboard/property_detail.html", {
        "property": prop,
        "images": prop.images.all(),
        "upload_form": PropertyImageUploadForm(),
        "review_form": PropertyReviewForm(),
        "leads": leads,
        "history": AuditLog.objects.filter(target_type="Property", target_id=str(prop.pk)).select_related("actor")[:15],
    })


@require_POST
@perm_required("properties.approve_property")
def property_review(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    form = PropertyReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose an action and add a reason when returning or rejecting.")
        return redirect("dashboard:property_detail", pk=pk)
    action, note = form.cleaned_data["action"], form.cleaned_data["note"]
    old = prop.status
    if action == "approve":
        prop.status = Property.Status.PUBLISHED
        prop.published_at = prop.published_at or timezone.now()
        audit, label = AuditLog.Action.APPROVE, "approved and published"
    elif action == "correction":
        prop.status = Property.Status.CORRECTION
        audit, label = AuditLog.Action.STATUS, "returned for correction"
    else:
        prop.status = Property.Status.REJECTED
        audit, label = AuditLog.Action.REJECT, "rejected"
    if note:
        prop.review_note = note
    prop.save()
    log_action(request, audit, prop, f"{old} → {prop.status}")
    if prop.owner_email and prop.source == Property.Source.OWNER:
        site = SiteSetting.load()
        body = f"Hello {prop.owner_name},\n\nYour property listing {prop.listing_id} (\"{prop.title}\") has been {label}."
        if prop.status == Property.Status.PUBLISHED:
            body += f"\n\nView it here: {request.build_absolute_uri(prop.get_absolute_url())}"
        elif note:
            body += f"\n\nNote from our team: {note}"
        notify(f"Your listing {prop.listing_id} has been {label}", body + f"\n\n– {site.brand_name}", [prop.owner_email])
    messages.success(request, f"Listing {label}.")
    return redirect("dashboard:property_detail", pk=pk)


@require_POST
@perm_required("properties.change_property")
def property_images_upload(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    form = PropertyImageUploadForm(request.POST, request.FILES)
    if form.is_valid():
        start = prop.images.count()
        has_primary = prop.images.filter(is_primary=True).exists()
        for i, photo in enumerate(form.cleaned_data["photos"]):
            PropertyImage.objects.create(property=prop, image=photo, sort_order=start + i,
                                         is_primary=not has_primary and i == 0, alt_text=prop.title[:160])
        log_action(request, AuditLog.Action.UPDATE, prop, f"Uploaded {len(form.cleaned_data['photos'])} photo(s)")
        messages.success(request, "Photos uploaded.")
    else:
        for err in form.errors.get("photos", []):
            messages.error(request, err)
    return redirect(f"{reverse('dashboard:property_detail', args=[pk])}#photos")


@require_POST
@perm_required("properties.change_property")
def property_image_action(request, pk, image_pk):
    image = get_object_or_404(PropertyImage, pk=image_pk, property_id=pk)
    action = request.POST.get("action")
    if action == "delete":
        was_primary = image.is_primary
        image.delete()
        if was_primary and (first := PropertyImage.objects.filter(property_id=pk).first()):
            first.is_primary = True
            first.save(update_fields=["is_primary"])
        messages.success(request, "Photo removed.")
    elif action == "primary":
        with transaction.atomic():
            PropertyImage.objects.filter(property_id=pk).update(is_primary=False)
            image.is_primary = True
            image.save(update_fields=["is_primary"])
        messages.success(request, "Main photo updated.")
    elif action == "update":
        image.alt_text = request.POST.get("alt_text", "")[:160]
        image.caption = request.POST.get("caption", "")[:160]
        try:
            image.sort_order = max(0, min(999, int(request.POST.get("sort_order", image.sort_order))))
        except ValueError:
            pass
        image.save(update_fields=["alt_text", "caption", "sort_order"])
        messages.success(request, "Photo details saved.")
    return redirect(f"{reverse('dashboard:property_detail', args=[pk])}#photos")


# --------------------------------------------------------------------------- leads


def _parse_date(value):
    try:
        return parse_date((value or "")[:10])
    except ValueError:
        return None


def _lead_queryset(request):
    qs = Lead.objects.visible_to(request.user).select_related("assigned_to", "interested_property", "interested_project")
    g = request.GET
    if q := g.get("q", "").strip()[:100]:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(lead_id__iexact=q) | Q(email__icontains=q))
    if g.get("status") in Lead.Status.values:
        qs = qs.filter(status=g["status"])
    if g.get("source") in Lead.Source.values:
        qs = qs.filter(source=g["source"])
    if g.get("priority") in Lead.Priority.values:
        qs = qs.filter(priority=g["priority"])
    if request.user.has_perm("leads.view_all_leads"):
        if g.get("assigned") == "none":
            qs = qs.filter(assigned_to__isnull=True)
        elif g.get("assigned", "").isdigit():
            qs = qs.filter(assigned_to_id=int(g["assigned"]))
    if date_from := _parse_date(g.get("date_from")):
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to := _parse_date(g.get("date_to")):
        qs = qs.filter(created_at__date__lte=date_to)
    if g.get("due") == "1":
        qs = qs.open().filter(next_follow_up__lte=timezone.localdate())
    if g.get("archived") != "1":
        qs = qs.filter(is_archived=False)
    return qs


@perm_required("leads.view_lead")
def lead_list(request):
    return render(request, "dashboard/lead_list.html", {
        "page_obj": _paginate(request, _lead_queryset(request)),
        "statuses": Lead.Status.choices,
        "sources": Lead.Source.choices,
        "priorities": Lead.Priority.choices,
        "staff": User.objects.filter(is_staff=True, is_active=True) if request.user.has_perm("leads.view_all_leads") else None,
        "today": timezone.localdate(),
    })


@perm_required("leads.export_lead")
def lead_export(request):
    qs = _lead_queryset(request).order_by("-created_at")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="leads-{timezone.localdate():%Y%m%d}.csv"'
    response.write("﻿")  # Excel-friendly UTF-8 BOM

    def cell(value):
        text = "" if value is None else str(value)
        # Neutralise spreadsheet formula injection.
        return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text

    writer = csv.writer(response)
    writer.writerow(["Lead ID", "Created", "Name", "Phone", "Email", "Requirement", "Source", "Status", "Priority",
                     "Property", "Budget min", "Budget max", "Preferred location", "Assigned to", "Next follow-up",
                     "Consent", "Campaign"])
    count = 0
    for lead in qs.iterator(chunk_size=500):
        count += 1
        writer.writerow([cell(v) for v in [
            lead.lead_id, timezone.localtime(lead.created_at).strftime("%Y-%m-%d %H:%M"), lead.name, lead.phone,
            lead.email, lead.get_requirement_display(), lead.get_source_display(), lead.get_status_display(),
            lead.get_priority_display(), lead.interested_property.listing_id if lead.interested_property else "",
            lead.budget_min, lead.budget_max, lead.preferred_location,
            lead.assigned_to or "", lead.next_follow_up or "", "Yes" if lead.consent else "No", lead.campaign,
        ]])
    filters = request.GET.urlencode()[:200]
    log_action(request, AuditLog.Action.EXPORT, target_type="Lead",
               description=f"Exported {count} leads" + (f" (filters: {filters})" if filters else " (no filters)"))
    return response


@perm_required("leads.view_lead")
def lead_detail(request, pk):
    lead = get_object_or_404(Lead.objects.visible_to(request.user).select_related(
        "assigned_to", "interested_property", "interested_project"), pk=pk)
    user = request.user
    update_form = LeadUpdateForm(instance=lead, prefix="u")
    note_form = LeadNoteForm(prefix="n")
    assign_form = LeadAssignForm(initial={"assigned_to": lead.assigned_to}, prefix="a")

    if request.method == "POST":
        action = request.POST.get("form")
        if action == "update":
            if not user.has_perm("leads.change_lead"):
                raise PermissionDenied
            old_status = lead.status
            update_form = LeadUpdateForm(request.POST, instance=lead, prefix="u")
            if update_form.is_valid():
                lead = update_form.save()
                if old_status != lead.status:
                    LeadStatusHistory.objects.create(lead=lead, from_status=old_status, to_status=lead.status, changed_by=user)
                    log_action(request, AuditLog.Action.STATUS, lead, f"{old_status} → {lead.status}")
                elif update_form.changed_data:
                    log_action(request, AuditLog.Action.UPDATE, lead, f"Changed: {', '.join(update_form.changed_data)}")
                messages.success(request, "Lead updated.")
                return redirect("dashboard:lead_detail", pk=pk)
        elif action == "note":
            if not user.has_perm("leads.add_leadnote"):
                raise PermissionDenied
            note_form = LeadNoteForm(request.POST, prefix="n")
            if note_form.is_valid():
                note = note_form.save(commit=False)
                note.lead, note.author = lead, user
                note.save()
                messages.success(request, "Note added.")
                return redirect("dashboard:lead_detail", pk=pk)
        elif action == "assign":
            if not user.has_perm("leads.assign_lead"):
                raise PermissionDenied
            assign_form = LeadAssignForm(request.POST, prefix="a")
            if assign_form.is_valid():
                new = assign_form.cleaned_data["assigned_to"]
                if new != lead.assigned_to:
                    lead.assigned_to = new
                    lead.save(update_fields=["assigned_to", "updated_at"])
                    LeadAssignment.objects.create(lead=lead, assigned_to=new, assigned_by=user)
                    log_action(request, AuditLog.Action.ASSIGN, lead, f"Assigned to {new or 'nobody'}")
                    if new and new.email:
                        notify(f"[Hamara Makaan] Lead {lead.lead_id} assigned to you",
                               f"Lead {lead.lead_id} has been assigned to you.\n\n"
                               f"{request.build_absolute_uri(reverse('dashboard:lead_detail', args=[lead.pk]))}",
                               [new.email])
                messages.success(request, "Assignment saved.")
                return redirect("dashboard:lead_detail", pk=pk)
        elif action == "archive":
            if not user.has_perm("leads.change_lead"):
                raise PermissionDenied
            lead.is_archived = not lead.is_archived
            lead.save(update_fields=["is_archived", "updated_at"])
            log_action(request, AuditLog.Action.UPDATE, lead, "Archived" if lead.is_archived else "Restored")
            messages.success(request, "Lead archived." if lead.is_archived else "Lead restored.")
            return redirect("dashboard:lead_detail", pk=pk)

    timeline = sorted(
        [("note", n.created_at, n) for n in lead.notes.select_related("author")]
        + [("status", h.created_at, h) for h in lead.status_history.select_related("changed_by")]
        + [("assign", a.created_at, a) for a in lead.assignments.select_related("assigned_to", "assigned_by")],
        key=lambda item: item[1], reverse=True,
    )
    return render(request, "dashboard/lead_detail.html", {
        "lead": lead, "update_form": update_form, "note_form": note_form, "assign_form": assign_form,
        "timeline": timeline,
    })


@perm_required("leads.add_lead")
def lead_create(request):
    form = LeadCreateForm(request.POST or None, user=request.user, initial={"source": Lead.Source.MANUAL})
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        if not request.user.has_perm("leads.view_all_leads") and not lead.assigned_to_id:
            lead.assigned_to = request.user  # so the creator can still see it
        lead.save()
        LeadStatusHistory.objects.create(lead=lead, to_status=lead.status, changed_by=request.user)
        if lead.assigned_to_id:
            LeadAssignment.objects.create(lead=lead, assigned_to=lead.assigned_to, assigned_by=request.user)
        log_action(request, AuditLog.Action.CREATE, lead, "Lead added manually")
        messages.success(request, "Lead added.")
        return redirect("dashboard:lead_detail", pk=lead.pk)
    return render(request, "dashboard/form_page.html", {"form": form, "title": "Add lead", "back": reverse("dashboard:lead_list")})


# --------------------------------------------------------------------------- users & roles


@perm_required("accounts.view_user")
def user_list(request):
    qs = User.objects.prefetch_related("groups").order_by("-is_active", "first_name", "username")
    if q := request.GET.get("q", "").strip()[:100]:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    return render(request, "dashboard/user_list.html", {"page_obj": _paginate(request, qs)})


def _guard_superuser_target(request, target):
    if target.is_superuser and not request.user.is_superuser:
        raise PermissionDenied


@perm_required("accounts.add_user")
def user_create(request):
    form = UserForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(request, AuditLog.Action.PERMISSION, user, f"Created staff user with role {form.cleaned_data.get('role') or 'none'}")
        messages.success(request, "Staff account created.")
        return redirect("dashboard:user_list")
    return render(request, "dashboard/form_page.html", {"form": form, "title": "Add staff member", "back": reverse("dashboard:user_list")})


@perm_required("accounts.change_user")
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_superuser_target(request, target)
    old_role = target.groups.first()
    form = UserForm(request.POST or None, instance=target, actor=request.user)
    if request.method == "POST" and form.is_valid():
        if target == request.user and not form.cleaned_data.get("is_active"):
            form.add_error("is_active", "You cannot deactivate your own account.")
        else:
            user = form.save()
            new_role = form.cleaned_data.get("role")
            if old_role != new_role:
                log_action(request, AuditLog.Action.PERMISSION, user, f"Role {old_role or 'none'} → {new_role or 'none'}")
            if "is_active" in form.changed_data:
                log_action(request, AuditLog.Action.PERMISSION, user, "Activated" if user.is_active else "Deactivated")
            messages.success(request, "Staff account saved.")
            return redirect("dashboard:user_list")
    return render(request, "dashboard/form_page.html", {
        "form": form, "title": f"Edit {target}", "back": reverse("dashboard:user_list"),
        "extra_link": (reverse("dashboard:user_password", args=[pk]), "Set a new password"),
    })


@perm_required("accounts.change_user")
def user_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_superuser_target(request, target)
    form = AdminSetPasswordForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, AuditLog.Action.PERMISSION, target, "Password reset by administrator")
        messages.success(request, "Password updated. Share it with the user through a secure channel.")
        return redirect("dashboard:user_list")
    return render(request, "dashboard/form_page.html", {"form": form, "title": f"Set password for {target}", "back": reverse("dashboard:user_list")})


# --------------------------------------------------------------------------- settings, reports, audit


@perm_required("core.change_sitesetting")
def site_settings(request):
    site = SiteSetting.load()
    site = SiteSetting.objects.get(pk=site.pk)  # fresh copy, not the cached one
    form = SiteSettingForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, AuditLog.Action.SETTINGS, site, f"Changed: {', '.join(form.changed_data)}"[:300])
        messages.success(request, "Settings saved.")
        return redirect("dashboard:settings")
    return render(request, "dashboard/settings.html", {
        "form": form,
        "smtp_configured": bool(settings.EMAIL_HOST) or "console" in settings.EMAIL_BACKEND,
        "email_backend": settings.EMAIL_BACKEND.rsplit(".", 1)[-1],
        "lead_recipients": len(settings.LEAD_NOTIFICATION_EMAILS),
    })


@perm_required("core.view_reports")
def reports(request):
    try:
        days = max(7, min(365, int(request.GET.get("days", 30))))
    except ValueError:
        days = 30
    since = timezone.now() - timedelta(days=days)
    leads = Lead.objects.filter(created_at__gte=since)
    today = timezone.localdate()
    staff_report = (
        User.objects.filter(is_staff=True, assigned_leads__isnull=False).distinct()
        .annotate(
            open_leads=Count("assigned_leads", filter=~Q(assigned_leads__status__in=Lead.CLOSED_STATUSES)),
            overdue=Count("assigned_leads", filter=Q(assigned_leads__next_follow_up__lt=today)
                          & ~Q(assigned_leads__status__in=Lead.CLOSED_STATUSES)),
            converted=Count("assigned_leads", filter=Q(assigned_leads__status=Lead.Status.CONVERTED)),
        )
    )
    by_day = leads.annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id")).order_by("-day")
    return render(request, "dashboard/reports.html", {
        "days": days,
        "total_leads": leads.count(),
        "by_day": by_day,
        "by_source": leads.values("source").annotate(n=Count("id")).order_by("-n"),
        "by_status": leads.values("status").annotate(n=Count("id")).order_by("-n"),
        "source_labels": dict(Lead.Source.choices),
        "status_labels": dict(Lead.Status.choices),
        "top_enquired": Property.objects.annotate(n=Count("leads", filter=Q(leads__created_at__gte=since)))
        .filter(n__gt=0).order_by("-n")[:10],
        "top_viewed": Property.objects.public().order_by("-view_count")[:10],
        "listing_status": Property.objects.values("status").annotate(n=Count("id")).order_by("-n"),
        "property_status_labels": dict(Property.Status.choices),
        "staff_report": staff_report,
        "whatsapp_clicks": WhatsAppClick.objects.filter(created_at__gte=since).count(),
    })


@perm_required("core.view_auditlog")
def audit_log(request):
    qs = AuditLog.objects.select_related("actor")
    if (action := request.GET.get("action", "")) in AuditLog.Action.values:
        qs = qs.filter(action=action)
    if q := request.GET.get("q", "").strip()[:100]:
        qs = qs.filter(Q(description__icontains=q) | Q(target_type__icontains=q) | Q(actor__username__icontains=q))
    return render(request, "dashboard/audit_log.html", {"page_obj": _paginate(request, qs, 50), "actions": AuditLog.Action.choices})


# --------------------------------------------------------------------------- generic CRUD


def _crud_or_404(slug):
    crud = CRUD_BY_SLUG.get(slug)
    if crud is None:
        raise Http404
    return crud


def _cell(obj, name):
    if name == "__str__":
        return str(obj)
    field = obj._meta.get_field(name)
    if field.choices:
        return getattr(obj, f"get_{name}_display")()
    value = getattr(obj, name)
    if isinstance(value, bool):
        return "✓" if value else "—"
    if value is None or value == "":
        return "—"
    if hasattr(value, "strftime"):
        return timezone.localtime(value).strftime("%d %b %Y, %H:%M") if hasattr(value, "hour") else value.strftime("%d %b %Y")
    return str(value)


@staff_required
def crud_list(request, slug):
    crud = _crud_or_404(slug)
    if not request.user.has_perm(crud.perm("view")):
        raise PermissionDenied
    qs = crud.model._default_manager.select_related(*crud.select_related)
    if (q := request.GET.get("q", "").strip()[:100]) and crud.search_fields:
        cond = Q()
        for f in crud.search_fields:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)
    filter_choices = None
    if crud.filter_field:
        filter_choices = crud.model._meta.get_field(crud.filter_field).choices
        if (val := request.GET.get("filter", "")) and val in dict(filter_choices):
            qs = qs.filter(**{crud.filter_field: val})
    page = _paginate(request, qs)
    headers = [crud.model._meta.get_field(n).verbose_name.capitalize() if n != "__str__" else crud.singular.capitalize()
               for n in crud.list_display]
    rows = [(obj, [_cell(obj, n) for n in crud.list_display]) for obj in page.object_list]
    return render(request, "dashboard/crud_list.html", {
        "crud": crud, "page_obj": page, "headers": headers, "rows": rows, "filter_choices": filter_choices,
        "can_add": request.user.has_perm(crud.perm("add")),
        "can_change": request.user.has_perm(crud.perm("change")),
    })


@staff_required
def crud_form(request, slug, pk=None):
    crud = _crud_or_404(slug)
    obj = get_object_or_404(crud.model, pk=pk) if pk else None
    if not request.user.has_perm(crud.perm("change" if obj else "add")):
        raise PermissionDenied
    form = crud.get_form_class()(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        instance = form.save(commit=False)
        if crud.before_save:
            crud.before_save(request, instance, obj is None)
        instance.save()
        form.save_m2m()
        log_action(request, AuditLog.Action.UPDATE if obj else AuditLog.Action.CREATE, instance,
                   f"{'Updated' if obj else 'Created'} {crud.singular}: {instance}"[:300])
        messages.success(request, f"{crud.singular.capitalize()} saved.")
        return redirect("dashboard:crud_list", slug=slug)
    return render(request, "dashboard/crud_form.html", {
        "crud": crud, "form": form, "object": obj,
        "can_delete": obj is not None and request.user.has_perm(crud.perm("delete")),
    })


@staff_required
def crud_delete(request, slug, pk):
    crud = _crud_or_404(slug)
    if not request.user.has_perm(crud.perm("delete")):
        raise PermissionDenied
    obj = get_object_or_404(crud.model, pk=pk)
    if request.method == "POST":
        label = str(obj)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(request, f"“{label}” is in use by other records and cannot be deleted. Deactivate it instead.")
            return redirect("dashboard:crud_edit", slug=slug, pk=pk)
        log_action(request, AuditLog.Action.DELETE, target_type=crud.singular.title(), target_id=pk, description=f"Deleted {label}"[:300])
        messages.success(request, f"{crud.singular.capitalize()} deleted.")
        return redirect("dashboard:crud_list", slug=slug)
    return render(request, "dashboard/confirm_delete.html", {"crud": crud, "object": obj})


def sidebar_groups(user):
    """Build the dashboard navigation from the user's permissions (UI only; views enforce access)."""
    groups = {}
    for crud in CRUDS:
        if user.has_perm(crud.perm("view")):
            groups.setdefault(crud.group, []).append((crud.title, reverse("dashboard:crud_list", args=[crud.slug]), crud.slug))
    return groups
