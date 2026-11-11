from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import cache_page

from apps.blog.models import BlogPost
from apps.leads.forms import CallbackForm
from apps.locations.models import City, Locality
from apps.pages.models import FAQ, Highlight, Service, Testimonial
from apps.properties.forms import RENT_BUDGETS, SALE_BUDGETS
from apps.properties.models import Project, Property, PropertyType

HOME_CATEGORY_TILES = [
    # (label, icon tile, URL name, query string)
    ("Apartments", "apartment", "properties:buy", "type=apartment"),
    ("Independent houses", "independent-house", "properties:buy", "type=independent-house"),
    ("Villas", "villa", "properties:buy", "type=villa"),
    ("Plots", "plot", "properties:buy", "type=residential-plot"),
    ("Homes for rent", "rent", "properties:rent", ""),
    ("Office space", "office-space", "properties:commercial", "type=office-space"),
    ("Shops & showrooms", "commercial-shop", "properties:commercial", "type=shop-showroom"),
    ("New projects", "new-projects", "properties:projects", ""),
]


def home(request):
    public = Property.objects.public().with_related()
    featured = list(public.filter(is_featured=True).order_by("-published_at")[:4])
    latest = list(public.exclude(pk__in=[p.pk for p in featured]).order_by("-published_at")[:8])
    cities = (
        City.objects.filter(is_active=True)
        .annotate(listing_count=Count("properties", filter=Q(properties__status__in=Property.PUBLIC_STATUSES)))
        .order_by("sort_order", "name")[:12]
    )
    tiles = [
        {"label": label, "tile": tile, "url": reverse(url) + (f"?{qs}" if qs else "")}
        for label, tile, url, qs in HOME_CATEGORY_TILES
    ]
    context = {
        "featured": featured,
        "latest": latest,
        "cities": cities,
        "tiles": tiles,
        "search_cities": City.objects.filter(is_active=True),
        "property_types": PropertyType.objects.filter(is_active=True),
        "popular_localities": Locality.objects.filter(is_active=True, is_popular=True).select_related("city")[:6],
        "sale_budgets": SALE_BUDGETS,
        "budget_presets": {"sale": SALE_BUDGETS, "rent": RENT_BUDGETS},
        "projects": Project.objects.public().select_related("city", "locality").filter(is_featured=True)[:3],
        "services": Service.objects.filter(is_published=True)[:6],
        "highlights": Highlight.objects.filter(is_published=True)[:4],
        "testimonials": Testimonial.objects.filter(is_published=True, permission_confirmed=True)[:3],
        "faqs": FAQ.objects.filter(is_published=True, show_on_home=True)[:6],
        "posts": BlogPost.objects.published().select_related("category")[:3],
        "callback_form": CallbackForm(),
    }
    return render(request, "pages/home.html", context)


@cache_page(60 * 60)
def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.DASHBOARD_PATH}",
        f"Disallow: /{settings.DJANGO_ADMIN_PATH}",
        "Disallow: /go/",
        "Disallow: /post-property/thank-you/",
        "",
        f"Sitemap: {request.build_absolute_uri(reverse('django.contrib.sitemaps.views.sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def error_404(request, exception=None):
    return render(request, "404.html", {"noindex": True}, status=404)


def error_500(request):
    # Rendered without context processors that touch the database.
    return render(request, "500.html", status=500)
