from django.conf import settings
from django.urls import reverse

from apps.core.utils import notify

from .models import Lead, LeadStatusHistory


def create_lead_from_form(request, form, source, **extra):
    """Save a lead from a validated public form."""
    return create_lead(request, form.save(commit=False), source, consent=bool(form.cleaned_data.get("consent")), **extra)


def create_lead(request, lead, source, consent, **extra):
    """Save an unsaved Lead, record its initial status and alert the team."""
    lead.source = source
    lead.source_url = request.build_absolute_uri()[:500]
    lead.campaign = request.session.get("utm_campaign", "")[:120]
    lead.consent = consent
    for key, value in extra.items():
        setattr(lead, key, value)
    lead.save()
    LeadStatusHistory.objects.create(lead=lead, to_status=lead.status)
    notify_new_lead(request, lead)
    return lead


def notify_new_lead(request, lead):
    lead.refresh_from_db(fields=["lead_id"])
    url = request.build_absolute_uri(reverse("dashboard:lead_detail", args=[lead.pk]))
    lines = [
        f"New {lead.get_source_display().lower()} received.",
        "",
        f"Lead ID: {lead.lead_id}",
        f"Requirement: {lead.get_requirement_display()}",
    ]
    if lead.interested_property_id:
        lines.append(f"Property: {lead.interested_property.listing_id} – {lead.interested_property.title}")
    if lead.interested_project_id:
        lines.append(f"Project: {lead.interested_project.name}")
    # Contact details stay inside the secure dashboard rather than in email.
    lines += ["", f"Open in dashboard: {url}"]
    notify(f"[Hamara Makaan] New lead {lead.lead_id}", "\n".join(lines), settings.LEAD_NOTIFICATION_EMAILS)
