from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.models import SiteSetting
from apps.core.utils import is_rate_limited, notify
from apps.leads.forms import EnquiryForm
from apps.leads.models import Lead
from apps.leads.services import create_lead, create_lead_from_form
from apps.locations.models import City

from .forms import RENT_BUDGETS, SALE_BUDGETS, PostPropertyForm, PropertySearchForm
from .models import Category, Project, Property, PropertyImage

SECTIONS = {
    "all": {
        "title": "Properties for sale and rent",
        "intro": "Browse approved homes, plots and commercial spaces.",
        "url": "properties:list",
    },
    "buy": {
        "title": "Property for sale",
        "intro": "Flats, houses, villas and plots for sale.",
        "url": "properties:buy",
    },
    "rent": {
        "title": "Property for rent",
        "intro": "Homes and commercial spaces available on rent or lease.",
        "url": "properties:rent",
    },
    "commercial": {
        "title": "Commercial property",
        "intro": "Offices, shops, showrooms, warehouses and commercial land.",
        "url": "properties:commercial",
    },
}


def _section_queryset(section):
    qs = Property.objects.public().with_related()
    if section == "buy":
        qs = qs.filter(purpose=Property.Purpose.SALE)
    elif section == "rent":
        qs = qs.filter(purpose__in=[Property.Purpose.RENT, Property.Purpose.LEASE])
    elif section == "commercial":
        qs = qs.filter(category=Category.COMMERCIAL)
    return qs


def property_list(request, section="all", city_slug=None):
    if "budget" in request.GET:
        # Expand a home-page budget preset into explicit, editable min/max filters.
        query = request.GET.copy()
        low, high = PropertySearchForm.parse_budget(query.pop("budget")[0])
        if low is not None:
            query["min_price"] = str(low)
        if high is not None:
            query["max_price"] = str(high)
        return redirect(f"{request.path}?{query.urlencode()}" if query else request.path)

    meta = dict(SECTIONS[section])
    meta["base_title"] = meta["title"]
    city = None
    qs = _section_queryset(section)
    if city_slug:
        city = get_object_or_404(City, slug=city_slug, is_active=True)
        qs = qs.filter(city=city)
        meta["title"] = f"{meta['title']} in {city.name}"

    form = PropertySearchForm(request.GET or None, city=city)
    qs = form.filter_queryset(qs)
    page = Paginator(qs, 12).get_page(request.GET.get("page"))

    filtered = form.is_bound and form.active_filter_count() > 0
    base_url = reverse(f"{meta['url']}_city", args=[city.slug]) if city else reverse(meta["url"])
    context = {
        "section": section,
        "meta": meta,
        "city": city,
        "form": form,
        "page_obj": page,
        "properties": page.object_list,
        "filter_count": form.active_filter_count() if form.is_bound else 0,
        "base_url": base_url,
        "budgets": RENT_BUDGETS if section == "rent" else SALE_BUDGETS,
        # Filtered and empty result pages are not indexed, to avoid thin/duplicate pages.
        "noindex": filtered or page.paginator.count == 0,
        "canonical_path": base_url + (f"?page={page.number}" if page.number > 1 and not filtered else ""),
        "section_cities": City.objects.filter(is_active=True, properties__status=Property.Status.PUBLISHED).distinct()[:12],
    }
    return render(request, "properties/list.html", context)


def _can_preview(user, perm="properties.view_property"):
    return user.is_authenticated and user.is_staff and user.has_perm(perm)


@require_http_methods(["GET", "POST"])
def property_detail(request, slug):
    prop = get_object_or_404(Property.objects.with_related().prefetch_related("amenities"), slug=slug)
    preview = not prop.is_public
    if preview and not _can_preview(request.user):
        raise Http404

    form = EnquiryForm(request.POST or None, initial={
        "message": f"I'm interested in {prop.title} ({prop.listing_id}). Please share more details."
    })
    if request.method == "POST":
        if preview:
            messages.error(request, "Enquiries are disabled in preview mode.")
        elif is_rate_limited(request, "enquiry"):
            messages.error(request, "Too many enquiries from your connection. Please try again in a few minutes.")
        elif form.is_valid():
            requirement = Lead.Requirement.RENT if prop.is_rental else Lead.Requirement.BUY
            create_lead_from_form(
                request, form, Lead.Source.PROPERTY, interested_property=prop,
                requirement=requirement, preferred_location=prop.location_label[:120],
            )
            messages.success(request, "Thank you! Your enquiry has been sent. Our team will contact you soon.")
            return redirect(f"{prop.get_absolute_url()}#enquire")
        else:
            messages.error(request, "Please correct the highlighted fields.")

    if not preview and request.method == "GET" and not request.user.is_staff:
        Property.objects.filter(pk=prop.pk).update(view_count=F("view_count") + 1)

    related = (
        Property.objects.public().with_related()
        .filter(city=prop.city, purpose=prop.purpose).exclude(pk=prop.pk).order_by("-is_featured", "-published_at")[:4]
    )
    section = "rent" if prop.is_rental else "buy"
    breadcrumbs = [
        ("Home", reverse("core:home")),
        ("Rent" if section == "rent" else "Buy", reverse(SECTIONS[section]["url"])),
        (prop.city.name, reverse(f"{SECTIONS[section]['url']}_city", args=[prop.city.slug])),
    ]
    if prop.locality and prop.locality.is_active:
        breadcrumbs.append((prop.locality.name, prop.locality.get_absolute_url()))
    breadcrumbs.append((prop.title, None))
    return render(request, "properties/detail.html", {
        "property": prop,
        "images": list(prop.images.all()),
        "form": form,
        "related": related,
        "preview": preview,
        "breadcrumbs": breadcrumbs,
        "noindex": preview,
    })


def project_list(request):
    qs = Project.objects.public().select_related("city", "locality")
    status = request.GET.get("status", "")
    city_slug = request.GET.get("city", "")
    if status in Project.Status.values:
        qs = qs.filter(status=status)
    if city_slug:
        qs = qs.filter(city__slug=city_slug)
    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    return render(request, "properties/project_list.html", {
        "page_obj": page,
        "projects": page.object_list,
        "statuses": Project.Status.choices,
        "cities": City.objects.filter(is_active=True, projects__is_published=True).distinct(),
        "current_status": status,
        "current_city": city_slug,
        "noindex": bool(status or city_slug),
    })


@require_http_methods(["GET", "POST"])
def project_detail(request, slug):
    project = get_object_or_404(Project.objects.select_related("city", "locality").prefetch_related("amenities"), slug=slug)
    preview = not project.is_published
    if preview and not _can_preview(request.user, "properties.view_project"):
        raise Http404
    form = EnquiryForm(request.POST or None, initial={"message": f"Please share details and pricing for {project.name}."})
    if request.method == "POST":
        if preview:
            messages.error(request, "Enquiries are disabled in preview mode.")
        elif is_rate_limited(request, "enquiry"):
            messages.error(request, "Too many enquiries from your connection. Please try again in a few minutes.")
        elif form.is_valid():
            create_lead_from_form(request, form, Lead.Source.PROJECT, interested_project=project,
                                  requirement=Lead.Requirement.BUY, preferred_location=project.location_label[:120])
            messages.success(request, "Thank you! Your enquiry has been sent. Our team will contact you soon.")
            return redirect(f"{project.get_absolute_url()}#enquire")
        else:
            messages.error(request, "Please correct the highlighted fields.")
    listings = Property.objects.public().with_related().filter(project_name__iexact=project.name)[:4]
    return render(request, "properties/project_detail.html", {
        "project": project, "form": form, "preview": preview, "listings": listings, "noindex": preview,
    })


@require_http_methods(["GET", "POST"])
def post_property(request):
    form = PostPropertyForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if is_rate_limited(request, "post-property", limit=3, window=3600):
            messages.error(request, "Too many submissions from your connection. Please try again later.")
        elif form.is_valid():
            with transaction.atomic():
                prop = form.save()
                for index, photo in enumerate(form.cleaned_data.get("photos") or []):
                    PropertyImage.objects.create(property=prop, image=photo, sort_order=index, is_primary=index == 0,
                                                 alt_text=prop.title[:160])
                prop.refresh_from_db()
                requirement = Lead.Requirement.SELL if prop.purpose == Property.Purpose.SALE else Lead.Requirement.LET_OUT
                create_lead(
                    request,
                    Lead(name=prop.owner_name, phone=prop.owner_phone, email=prop.owner_email),
                    Lead.Source.POST_PROPERTY,
                    consent=True,
                    interested_property=prop,
                    requirement=requirement,
                    priority=Lead.Priority.HIGH,
                    preferred_location=prop.location_label[:120],
                )
            if prop.owner_email:
                site = SiteSetting.load()
                notify(
                    f"We received your property – reference {prop.listing_id}",
                    f"Hello {prop.owner_name},\n\nThank you for sharing your property \"{prop.title}\" with "
                    f"{site.brand_name}. Your reference number is {prop.listing_id}.\n\nOur team will review the "
                    "details and may contact you to confirm them. The listing goes live only after approval.\n\n"
                    f"– {site.brand_name}",
                    [prop.owner_email],
                )
            request.session["submitted_listing"] = prop.listing_id
            return redirect("properties:post_property_thanks")
        else:
            messages.error(request, "Please correct the highlighted fields and re-attach your photos.")
    return render(request, "properties/post_property.html", {"form": form})


def post_property_thanks(request):
    reference = request.session.pop("submitted_listing", None)
    if not reference:
        return redirect("properties:post_property")
    return render(request, "properties/post_property_thanks.html", {"reference": reference, "noindex": True})
