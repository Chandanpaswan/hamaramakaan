from django.contrib import admin

from .models import Lead, LeadNote, LeadStatusHistory, WhatsAppClick


class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 0


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("lead_id", "name", "source", "status", "assigned_to", "created_at")
    list_filter = ("status", "source")
    search_fields = ("lead_id", "name", "phone")
    inlines = [LeadNoteInline]


admin.site.register(LeadStatusHistory)
admin.site.register(WhatsAppClick)
