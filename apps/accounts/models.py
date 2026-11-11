from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import phone_validator


class User(AbstractUser):
    """Custom user from day one so phone login or extra profile fields can be added without a painful migration."""

    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    designation = models.CharField(max_length=80, blank=True, help_text="Shown internally, e.g. Sales Executive")

    class Meta:
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def role_names(self):
        if self.is_superuser:
            return ["Super Admin"]
        return [g.name for g in self.groups.all()]
