from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS

admin.site.site_header = "Hamara Makaan – System admin"
admin.site.site_title = "Hamara Makaan admin"

urlpatterns = [
    path(settings.DJANGO_ADMIN_PATH, admin.site.urls),
    path(settings.DASHBOARD_PATH, include("apps.dashboard.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    path("", include("apps.core.urls")),
    path("", include("apps.properties.urls")),
    path("", include("apps.leads.urls")),
    path("", include("apps.pages.urls")),
    path("locations/", include("apps.locations.urls")),
    path("blog/", include("apps.blog.urls")),
]

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
