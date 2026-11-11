from django.contrib import admin

from .models import AuditLog, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id", "ip_address")
    list_filter = ("action",)
    search_fields = ("description", "target_type", "actor__username")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
