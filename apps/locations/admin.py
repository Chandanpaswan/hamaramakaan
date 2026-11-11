from django.contrib import admin

from .models import City, Locality, State

admin.site.register(State)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "is_active", "is_indexable")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "is_active", "is_popular")
    list_filter = ("city",)
    search_fields = ("name",)
