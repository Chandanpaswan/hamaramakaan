from django.contrib import admin

from .models import BlogCategory, BlogPost, BlogTag


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "published_at", "category")
    list_filter = ("status", "category")
    search_fields = ("title",)


admin.site.register(BlogCategory)
admin.site.register(BlogTag)
