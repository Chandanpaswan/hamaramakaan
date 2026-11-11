from django.contrib import admin

from .models import Amenity, Project, Property, PropertyImage, PropertyType


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("listing_id", "title", "purpose", "city", "status", "is_featured", "published_at")
    list_filter = ("status", "purpose", "category", "city")
    search_fields = ("listing_id", "title", "owner_phone")
    readonly_fields = ("listing_id", "view_count", "verified_at", "verified_by")
    inlines = [PropertyImageInline]


admin.site.register(PropertyType)
admin.site.register(Amenity)
admin.site.register(Project)
