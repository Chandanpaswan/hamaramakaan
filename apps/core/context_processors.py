from django.conf import settings
from django.core.cache import cache

from .models import SiteSetting


def _footer_data():
    data = cache.get("hm:footer-data")
    if data is None:
        from apps.locations.models import City
        from apps.pages.models import Page

        data = {
            "footer_cities": list(City.objects.filter(is_active=True, show_in_footer=True).order_by("sort_order", "name")[:8]),
            "footer_pages": list(
                Page.objects.filter(is_published=True, show_in_footer=True).order_by("sort_order", "title")
            ),
        }
        cache.set("hm:footer-data", data, 300)
    return data


def canonical_base(request):
    """One canonical origin for canonical tags, og:url and JSON-LD, so extra hostnames
    (e.g. several *.vercel.app aliases) never compete as duplicate content."""
    if settings.DEBUG:
        return f"{request.scheme}://{request.get_host()}"
    domain = cache.get("hm:canonical-domain")
    if domain is None:
        from django.contrib.sites.models import Site

        domain = Site.objects.get_current().domain
        cache.set("hm:canonical-domain", domain, 3600)
    if domain in ("", "example.com"):
        return f"{request.scheme}://{request.get_host()}"
    return f"https://{domain}"


def site(request):
    path = request.path
    is_dashboard = path.startswith(f"/{settings.DASHBOARD_PATH}")
    context = {
        "canonical_base": canonical_base(request),
        "site": (site_settings := SiteSetting.load()),
        "brand_short": site_settings.brand_name.removesuffix(" Properties"),  # short suffix keeps <title> under ~60-70 chars
        "DASHBOARD_PATH": settings.DASHBOARD_PATH,
        "DEBUG": settings.DEBUG,
        "is_dashboard": is_dashboard,
    }
    if not is_dashboard:
        context.update(_footer_data())
    return context
