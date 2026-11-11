from django.conf import settings
from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models

from .utils import safe_upload_path

SITE_SETTINGS_CACHE_KEY = "hm:site-settings"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SEOFieldsMixin(models.Model):
    seo_title = models.CharField(
        "SEO title", max_length=70, blank=True, help_text="Leave blank to use the default title. Max 70 characters."
    )
    seo_description = models.CharField(
        "Meta description", max_length=170, blank=True, help_text="One or two sentences, max ~160 characters."
    )

    class Meta:
        abstract = True


phone_validator = RegexValidator(
    r"^\+?[0-9][0-9 \-]{7,16}$", "Enter a valid phone number (digits, spaces or dashes, optional leading +)."
)
ga4_validator = RegexValidator(r"^G-[A-Z0-9]{4,16}$", "GA4 measurement IDs look like G-XXXXXXXXXX.")


class SiteSetting(TimeStampedModel):
    """Single row of business-editable settings. Contact fields stay blank until verified by the business."""

    brand_name = models.CharField(max_length=120, default="Hamara Makaan Properties")
    tagline_hindi = models.CharField(max_length=120, default="सच होंगे सबके सपने", blank=True)
    tagline_english = models.CharField(max_length=120, default="Every dream, a home.", blank=True)

    phone = models.CharField(
        max_length=20, blank=True, validators=[phone_validator], help_text="Verified business phone, e.g. +91 98xxxxxxxx"
    )
    whatsapp_number = models.CharField(
        max_length=20, blank=True, validators=[phone_validator], help_text="Verified WhatsApp Business number with country code."
    )
    email = models.EmailField(blank=True, help_text="Official business email.")
    address = models.TextField(blank=True, help_text="Exact current office address.")
    office_hours = models.CharField(max_length=120, blank=True, help_text="e.g. Mon–Sat, 10:00 am – 7:00 pm")
    map_embed_url = models.URLField(
        max_length=600, blank=True, help_text="Google Maps 'Embed a map' src URL for the public office location."
    )

    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    x_url = models.URLField("X / Twitter URL", blank=True)

    hero_heading = models.CharField(max_length=120, default="Find a home that’s truly yours.")
    hero_subheading = models.CharField(
        max_length=240,
        default="Buy, rent or sell property in Faridabad and Delhi NCR with honest advice from a local team.",
    )
    hero_image = models.ImageField(
        "Banner image", upload_to=safe_upload_path("site"), blank=True,
        help_text="Home page banner photo (landscape, at least 1200 px wide). Leave empty to use the placeholder photo.",
    )
    hero_image_alt = models.CharField("Banner image description", max_length=160, blank=True,
                                      help_text="Describe the photo for screen readers, e.g. 'Family home with a garden in Faridabad'.")
    cta_heading = models.CharField(max_length=120, default="Ready to list your property?")
    cta_text = models.CharField(
        max_length=240,
        default="Share your property details and our team will review them and get back to you.",
    )
    footer_about = models.TextField(
        default="Hamara Makaan Properties helps families buy, sell and rent homes, plots and commercial space.",
    )

    default_meta_description = models.CharField(
        max_length=170,
        default="Find property for sale and rent in Faridabad and Delhi NCR with Hamara Makaan Properties.",
    )
    ga4_measurement_id = models.CharField("GA4 measurement ID", max_length=24, blank=True, validators=[ga4_validator])
    search_console_verification = models.CharField(
        max_length=120, blank=True, help_text="Content value of the google-site-verification meta tag."
    )

    maintenance_mode = models.BooleanField(
        default=False, help_text="Show a maintenance page to the public. Staff can still use the site."
    )
    maintenance_message = models.CharField(
        max_length=240, default="We are making some improvements. Please check back shortly.", blank=True
    )

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def delete(self, *args, **kwargs):  # The singleton row is never deleted.
        return

    @classmethod
    def load(cls):
        obj = cache.get(SITE_SETTINGS_CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(SITE_SETTINGS_CACHE_KEY, obj, 300)
        return obj

    @property
    def whatsapp_digits(self):
        return "".join(ch for ch in self.whatsapp_number if ch.isdigit())

    @property
    def phone_href(self):
        return "".join(ch for ch in self.phone if ch.isdigit() or ch == "+")

    @property
    def social_links(self):
        pairs = [
            ("Facebook", self.facebook_url),
            ("Instagram", self.instagram_url),
            ("LinkedIn", self.linkedin_url),
            ("YouTube", self.youtube_url),
            ("X", self.x_url),
        ]
        return [(label, url) for label, url in pairs if url]


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGIN_FAILED = "login_failed", "Failed login"
        LOGOUT = "logout", "Logout"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        STATUS = "status", "Status change"
        ASSIGN = "assign", "Assignment"
        EXPORT = "export", "Data export"
        PERMISSION = "permission", "Permission change"
        SETTINGS = "settings", "Settings change"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=300, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_reports", "Can view reports")]

    def __str__(self):
        return f"{self.get_action_display()} · {self.target_type} {self.target_id}".strip()
