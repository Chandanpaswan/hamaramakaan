from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel, phone_validator


class LeadQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Staff see only their assigned leads unless they hold `leads.view_all_leads`."""
        if not user.is_authenticated:
            return self.none()
        if user.is_superuser or user.has_perm("leads.view_all_leads"):
            return self
        return self.filter(assigned_to=user)

    def open(self):
        return self.exclude(status__in=Lead.CLOSED_STATUSES)


class Lead(TimeStampedModel):
    class Requirement(models.TextChoices):
        BUY = "buy", "Buy"
        RENT = "rent", "Rent"
        SELL = "sell", "Sell"
        LET_OUT = "let_out", "Rent out / lease"
        COMMERCIAL = "commercial", "Commercial"
        SITE_VISIT = "site_visit", "Site visit"
        CALLBACK = "callback", "Callback"
        GENERAL = "general", "General enquiry"

    class Source(models.TextChoices):
        PROPERTY = "property", "Property enquiry"
        PROJECT = "project", "Project enquiry"
        CONTACT = "contact", "Contact page"
        CALLBACK = "callback", "Callback request"
        POST_PROPERTY = "post_property", "Post Property form"
        PHONE = "phone", "Phone call campaign"
        BLOG = "blog", "Blog / landing page"
        WALK_IN = "walk_in", "Walk-in / referral"
        MANUAL = "manual", "Added by staff"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        SITE_VISIT = "site_visit", "Site visit scheduled"
        NEGOTIATION = "negotiation", "Negotiation"
        CONVERTED = "converted", "Converted"
        NOT_INTERESTED = "not_interested", "Not interested"
        INVALID = "invalid", "Invalid"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class ContactMethod(models.TextChoices):
        PHONE = "phone", "Phone call"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"

    CLOSED_STATUSES = (Status.CONVERTED, Status.NOT_INTERESTED, Status.INVALID, Status.CLOSED)

    lead_id = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField(blank=True)
    requirement = models.CharField(max_length=20, choices=Requirement.choices, default=Requirement.GENERAL)
    message = models.TextField(blank=True)
    interested_property = models.ForeignKey(
        "properties.Property", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    interested_project = models.ForeignKey(
        "properties.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    preferred_location = models.CharField(max_length=120, blank=True)
    preferred_contact_method = models.CharField(max_length=10, choices=ContactMethod.choices, default=ContactMethod.PHONE)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CONTACT, db_index=True)
    source_url = models.CharField(max_length=500, blank=True)
    campaign = models.CharField(max_length=120, blank=True, help_text="utm_campaign or campaign name")

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    next_follow_up = models.DateField(null=True, blank=True, db_index=True)

    consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("view_all_leads", "Can view all leads (not only assigned)"),
            ("assign_lead", "Can assign and reassign leads"),
            ("export_lead", "Can export leads to CSV"),
        ]
        indexes = [
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["phone"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(budget_min__isnull=True) | Q(budget_max__isnull=True) | Q(budget_max__gte=models.F("budget_min")),
                name="lead_budget_range_valid",
            )
        ]

    def __str__(self):
        return f"{self.lead_id} · {self.name}"

    def save(self, *args, **kwargs):
        if self.consent and not self.consent_at:
            self.consent_at = timezone.now()
        super().save(*args, **kwargs)
        if not self.lead_id:
            self.lead_id = f"L{self.pk:06d}"
            Lead.objects.filter(pk=self.pk).update(lead_id=self.lead_id)

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES

    @property
    def follow_up_overdue(self):
        return bool(self.next_follow_up and self.is_open and self.next_follow_up < timezone.localdate())


class LeadNote(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LeadStatusHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, choices=Lead.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Lead.Status.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "lead status history"


class LeadAssignment(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="assignments")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class WhatsAppClick(models.Model):
    """Records that a visitor clicked a WhatsApp button. No chat content is ever stored."""

    property = models.ForeignKey("properties.Property", null=True, blank=True, on_delete=models.SET_NULL)
    project = models.ForeignKey("properties.Project", null=True, blank=True, on_delete=models.SET_NULL)
    page_path = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
