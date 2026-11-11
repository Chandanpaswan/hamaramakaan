from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from apps.properties.models import Property

from .models import City, Locality

PUBLISHED = Q(properties__status=Property.Status.PUBLISHED)


def city_detail(request, city_slug):
    city = get_object_or_404(City, slug=city_slug, is_active=True)
    listings = Property.objects.public().with_related().filter(city=city).order_by("-is_featured", "-published_at")
    page = Paginator(listings, 12).get_page(request.GET.get("page"))
    localities = (
        city.localities.filter(is_active=True).annotate(listing_count=Count("properties", filter=PUBLISHED))
        .filter(listing_count__gt=0).order_by("-listing_count", "name")
    )
    return render(request, "locations/detail.html", {
        "city": city,
        "place": city,
        "page_obj": page,
        "properties": page.object_list,
        "localities": localities,
        "sale_count": listings.filter(purpose=Property.Purpose.SALE).count(),
        "rent_count": listings.exclude(purpose=Property.Purpose.SALE).count(),
        # Empty or opted-out location pages are noindexed (no thin pages).
        "noindex": not city.is_indexable or page.paginator.count == 0,
    })


def locality_detail(request, city_slug, locality_slug):
    locality = get_object_or_404(
        Locality.objects.select_related("city"), city__slug=city_slug, slug=locality_slug, is_active=True, city__is_active=True
    )
    listings = Property.objects.public().with_related().filter(locality=locality).order_by("-is_featured", "-published_at")
    page = Paginator(listings, 12).get_page(request.GET.get("page"))
    return render(request, "locations/detail.html", {
        "city": locality.city,
        "locality": locality,
        "place": locality,
        "page_obj": page,
        "properties": page.object_list,
        "sale_count": listings.filter(purpose=Property.Purpose.SALE).count(),
        "rent_count": listings.exclude(purpose=Property.Purpose.SALE).count(),
        "noindex": not locality.is_indexable or page.paginator.count == 0,
    })
