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


def site(request):
    path = request.path
    is_dashboard = path.startswith(f"/{settings.DASHBOARD_PATH}")
    context = {
        "site": SiteSetting.load(),
        "DASHBOARD_PATH": settings.DASHBOARD_PATH,
        "DEBUG": settings.DEBUG,
        "is_dashboard": is_dashboard,
    }
    if not is_dashboard:
        context.update(_footer_data())
    return context
