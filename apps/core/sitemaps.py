from django.contrib.sitemaps import Sitemap
from django.db.models import Count, Q
from django.urls import reverse

from apps.blog.models import BlogPost
from apps.locations.models import City, Locality
from apps.pages.models import Page
from apps.properties.models import Project, Property


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return ["core:home", "properties:list", "properties:buy", "properties:rent", "properties:commercial",
                "properties:projects", "properties:post_property", "blog:list", "pages:contact", "pages:faq"]

    def location(self, item):
        return reverse(item)


class PropertySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        return Property.objects.public().only("slug", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class ProjectSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Project.objects.public().only("slug", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class BlogSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return BlogPost.objects.published().only("slug", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.4

    def items(self):
        return Page.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


class LocationSitemap(Sitemap):
    """Only locations that are indexable *and* have live inventory, to avoid thin pages."""

    changefreq = "weekly"
    priority = 0.6
    published = Q(properties__status=Property.Status.PUBLISHED)

    def items(self):
        cities = City.objects.filter(is_active=True, is_indexable=True).annotate(n=Count("properties", filter=self.published)).filter(n__gt=0)
        localities = (
            Locality.objects.filter(is_active=True, is_indexable=True, city__is_active=True)
            .select_related("city").annotate(n=Count("properties", filter=self.published)).filter(n__gt=0)
        )
        return list(cities) + list(localities)


SITEMAPS = {
    "static": StaticSitemap,
    "properties": PropertySitemap,
    "projects": ProjectSitemap,
    "locations": LocationSitemap,
    "blog": BlogSitemap,
    "pages": PageSitemap,
}
