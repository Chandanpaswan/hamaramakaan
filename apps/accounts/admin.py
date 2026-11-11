from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("Profile", {"fields": ("phone", "designation")}),)
    list_display = ("username", "get_full_name", "email", "is_active", "is_staff", "last_login")
