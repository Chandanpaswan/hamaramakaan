from urllib.parse import quote

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.models import SiteSetting
from apps.core.utils import is_rate_limited
from apps.properties.models import Project, Property

from .forms import CallbackForm
from .models import Lead, WhatsAppClick
from .services import create_lead_from_form


def _safe_next(request, fallback="/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


@require_http_methods(["GET", "POST"])
def callback_request(request):
    form = CallbackForm(request.POST or None)
    if request.method == "POST":
        if is_rate_limited(request, "callback"):
            messages.error(request, "Too many requests from your connection. Please try again in a few minutes.")
        elif form.is_valid():
            create_lead_from_form(request, form, Lead.Source.CALLBACK, requirement=Lead.Requirement.CALLBACK)
            messages.success(request, "Thanks! We'll call you back soon.")
            return redirect(_safe_next(request))
        else:
            messages.error(request, "Please correct the highlighted fields.")
    return render(request, "leads/callback.html", {"form": form, "next": _safe_next(request), "noindex": True})


@require_GET
def whatsapp_redirect(request):
    """Log the click (never chat content) and hand off to WhatsApp click-to-chat."""
    site = SiteSetting.load()
    if not site.whatsapp_digits:
        return redirect("pages:contact")
    prop = project = None
    if listing_id := request.GET.get("property", "")[:12]:
        prop = Property.objects.public().filter(listing_id=listing_id).first()
    if slug := request.GET.get("project", "")[:160]:
        project = Project.objects.public().filter(slug=slug).first()
    referer = request.META.get("HTTP_REFERER", "")
    path = referer if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}) else ""
    WhatsAppClick.objects.create(property=prop, project=project, page_path=path[:300])

    if prop:
        text = f"Hi, I'm interested in {prop.title} (ID {prop.listing_id}): {request.build_absolute_uri(prop.get_absolute_url())}"
    elif project:
        text = f"Hi, I'd like details about {project.name}: {request.build_absolute_uri(project.get_absolute_url())}"
    else:
        text = f"Hi {site.brand_name}, I have a property enquiry."
    return redirect(f"https://wa.me/{site.whatsapp_digits}?text={quote(text)}")
