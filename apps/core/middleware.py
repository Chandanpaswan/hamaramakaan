from django.conf import settings
from django.shortcuts import render


class CampaignMiddleware:
    """Remember utm_campaign for the session so leads can be attributed to marketing campaigns."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        campaign = request.GET.get("utm_campaign")
        if campaign and hasattr(request, "session"):
            request.session["utm_campaign"] = campaign[:120]
        return self.get_response(request)


class MaintenanceModeMiddleware:
    """When maintenance mode is on, the public sees a 503 page; staff, the dashboard and assets keep working."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_prefixes = (
            f"/{settings.DASHBOARD_PATH}",
            f"/{settings.DJANGO_ADMIN_PATH}",
            settings.STATIC_URL,
            settings.MEDIA_URL,
            "/robots.txt",
        )

    def __call__(self, request):
        from apps.core.models import SiteSetting

        if not request.path.startswith(self.exempt_prefixes):
            site = SiteSetting.load()
            user = getattr(request, "user", None)
            if site.maintenance_mode and not (user and user.is_authenticated and user.is_staff):
                response = render(request, "maintenance.html", {"site": site}, status=503)
                response["Retry-After"] = "3600"
                return response
        return self.get_response(request)
